import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from config.settings import Settings
from db.models import (
    AnalyticsSEO,
    AnalyticsTraffic,
    Contenu,
    Post,
    ProjectDAHistory,
    Projet,
)
from services.da_fetcher import DAFetcher
from services.ga4_client import GA4Client
from services.google_auth import get_google_credentials
from services.gsc_client import GSCClient
from services.telegram_notifier import TelegramNotifier

logger = logging.getLogger("diffusionbot.worker.analytics")


class AnalyticsWorker:
    """Worker hebdomadaire: pull GA4 + GSC + Moz, stocke en DB."""

    def __init__(
        self,
        db_session: Session,
        da_fetcher: DAFetcher,
        notifier: TelegramNotifier,
        settings: Settings,
    ):
        self.db = db_session
        self.da_fetcher = da_fetcher
        self.notifier = notifier
        self.settings = settings

    async def run(self) -> dict:
        stats = {
            "total_sessions": 0,
            "total_users": 0,
            "total_clicks": 0,
            "top_platforms": [],
            "position_changes": [],
            "da_updates": 0,
        }

        projets = (
            self.db.execute(select(Projet).where(Projet.actif.is_(True))).scalars().all()
        )

        # Google credentials (partagees entre GA4 et GSC)
        creds = get_google_credentials(
            service_account_file=self.settings.google_service_account_file,
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
        )

        week_start = date.today() - timedelta(days=7)
        week_end = date.today()

        for projet in projets:
            logger.info(f"[{projet.slug}] Collecte analytics...")

            # ── GA4: traffic UTM ──
            if creds and projet.ga4_property_id:
                await self._collect_ga4(projet, creds, week_start, week_end, stats)

            # ── GSC: positions/clics ──
            if creds and projet.gsc_site_url:
                await self._collect_gsc(projet, creds, week_start, week_end, stats)

            # ── Moz: DA de notre domaine ──
            await self._collect_da(projet, stats)

        # Rapport Telegram
        await self.notifier.send_weekly_analytics(stats)
        logger.info(
            f"Analytics termine: {stats['total_sessions']} sessions, "
            f"{stats['total_clicks']} clics GSC, {stats['da_updates']} DA mis a jour"
        )
        return stats

    async def _collect_ga4(
        self, projet: Projet, creds, start: date, end: date, stats: dict
    ):
        """Collecte traffic GA4 par UTM et stocke dans analytics_traffic."""
        try:
            ga4 = GA4Client(creds, projet.ga4_property_id)
            rows = ga4.get_traffic_by_utm(start, end)

            platform_sessions = {}

            for row in rows:
                # Trouver le post_id depuis utm_content
                post_id = None
                if row.get("post_id"):
                    try:
                        post_id = int(row["post_id"])
                    except (ValueError, TypeError):
                        pass

                # Trouver la plateforme depuis utm_source
                post = None
                if post_id:
                    post = self.db.execute(
                        select(Post).where(Post.id == post_id)
                    ).scalar_one_or_none()

                plateforme_id = post.plateforme_id if post else None

                if post_id and plateforme_id:
                    record = AnalyticsTraffic(
                        post_id=post_id,
                        projet_id=projet.id,
                        plateforme_id=plateforme_id,
                        date=datetime.combine(end, datetime.min.time()).replace(tzinfo=timezone.utc),
                        sessions=row["sessions"],
                        users=row["users"],
                        bounce_rate=row["bounce_rate"],
                        avg_session_duration=row["avg_duration"],
                        conversions=row["conversions"],
                    )
                    self.db.add(record)

                # Aggreger par plateforme pour le rapport
                source = row["source"]
                platform_sessions[source] = platform_sessions.get(source, 0) + row["sessions"]

                stats["total_sessions"] += row["sessions"]
                stats["total_users"] += row["users"]

            self.db.commit()

            # Top plateformes pour le rapport
            sorted_platforms = sorted(platform_sessions.items(), key=lambda x: x[1], reverse=True)
            for name, sessions in sorted_platforms[:5]:
                stats["top_platforms"].append({"name": name, "sessions": sessions})

            logger.info(f"[{projet.slug}] GA4: {len(rows)} lignes UTM importees")

        except Exception as e:
            logger.error(f"[{projet.slug}] GA4 erreur: {e}")

    async def _collect_gsc(
        self, projet: Projet, creds, start: date, end: date, stats: dict
    ):
        """Collecte positions GSC et stocke dans analytics_seo."""
        try:
            gsc = GSCClient(creds, projet.gsc_site_url)

            # Performance par page
            pages = gsc.get_page_performance(start, end)
            aggregated = gsc.get_aggregated_performance(start, end)

            for page_data in pages:
                record = AnalyticsSEO(
                    projet_id=projet.id,
                    page_url=page_data["page"],
                    date=datetime.combine(end, datetime.min.time()).replace(tzinfo=timezone.utc),
                    clicks=page_data["clicks"],
                    impressions=page_data["impressions"],
                    avg_position=page_data["position"],
                )
                self.db.add(record)

            # Detecter les mouvements de position (compare avec la semaine precedente)
            prev_start = start - timedelta(days=7)
            prev_pages = gsc.get_page_performance(prev_start, start)
            prev_positions = {p["page"]: p["position"] for p in prev_pages}

            for page_data in pages[:10]:
                prev_pos = prev_positions.get(page_data["page"])
                if prev_pos:
                    delta = prev_pos - page_data["position"]  # Positif = amelioration
                    if abs(delta) >= 1:
                        short_page = page_data["page"].split("/")[-1] or page_data["page"]
                        stats["position_changes"].append({
                            "page": short_page[:40],
                            "delta": round(delta, 1),
                        })

            stats["total_clicks"] += aggregated["clicks"]

            self.db.commit()
            logger.info(f"[{projet.slug}] GSC: {len(pages)} pages importees")

        except Exception as e:
            logger.error(f"[{projet.slug}] GSC erreur: {e}")

    async def _collect_da(self, projet: Projet, stats: dict):
        """Recupere le DA de notre propre domaine et stocke dans project_da_history."""
        try:
            result = await self.da_fetcher.fetch_da(projet.domaine)
            if result:
                record = ProjectDAHistory(
                    projet_id=projet.id,
                    da_value=result["da"],
                    source=result["source"],
                    measured_at=datetime.now(timezone.utc),
                )
                self.db.add(record)
                self.db.commit()
                stats["da_updates"] += 1
                logger.info(f"[{projet.slug}] DA: {result['da']} ({result['source']})")
        except Exception as e:
            logger.error(f"[{projet.slug}] DA fetch erreur: {e}")
