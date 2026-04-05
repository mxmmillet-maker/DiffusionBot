import logging
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Plateforme, PlatformDAHistory, Post
from services.da_fetcher import DAFetcher
from services.scoring import PlatformMetrics, PlatformScorer
from services.telegram_notifier import TelegramNotifier

logger = logging.getLogger("diffusionbot.worker.intelligence")

# Plateformes avec survie < ce seuil sont desactivees automatiquement
AUTO_DISABLE_SURVIVAL_THRESHOLD = 0.5
# Nombre minimum de posts avant de juger une plateforme
MIN_POSTS_FOR_JUDGMENT = 3


class IntelligenceWorker:
    """Worker mensuel: analyse DA, tendances, scoring, nettoyage."""

    def __init__(
        self,
        db_session: Session,
        da_fetcher: DAFetcher,
        scorer: PlatformScorer,
        notifier: TelegramNotifier,
    ):
        self.db = db_session
        self.da_fetcher = da_fetcher
        self.scorer = scorer
        self.notifier = notifier

    async def run(self) -> dict:
        stats = {
            "analyzed": 0,
            "da_updated": 0,
            "scores_updated": 0,
            "disabled": 0,
            "rising": [],
            "declining": [],
        }

        plateformes = (
            self.db.execute(select(Plateforme).where(Plateforme.actif.is_(True)))
            .scalars()
            .all()
        )
        logger.info(f"Intelligence: analyse de {len(plateformes)} plateformes actives")

        for plateforme in plateformes:
            stats["analyzed"] += 1

            # 1. Fetch DA actuel
            da_result = await self._fetch_and_store_da(plateforme)
            if da_result:
                stats["da_updated"] += 1

            # 2. Calculer tendance DA
            trend = self._calculate_da_trend(plateforme.id)

            # 3. Calculer metriques et score
            metrics = self._build_metrics(plateforme, trend)
            new_score = self.scorer.calculate_score(metrics)
            plateforme.score_composite = new_score
            stats["scores_updated"] += 1

            # 4. Classifier rising/declining
            if trend is not None:
                entry = {
                    "name": plateforme.nom,
                    "da": plateforme.da_actuel or 0,
                    "trend": round(trend, 2),
                    "score": new_score,
                }
                if trend > 1:
                    stats["rising"].append(entry)
                elif trend < -1:
                    stats["declining"].append(entry)

        self.db.commit()

        # 5. Auto-desactiver les plateformes sous-performantes
        disabled = self._auto_disable_platforms()
        stats["disabled"] = len(disabled)

        # Trier rising/declining par amplitude
        stats["rising"].sort(key=lambda x: x["trend"], reverse=True)
        stats["declining"].sort(key=lambda x: x["trend"])

        # Rapport
        await self.notifier.send_monthly_intelligence(stats)
        logger.info(
            f"Intelligence termine: {stats['analyzed']} analysees, "
            f"{stats['da_updated']} DA mis a jour, {stats['disabled']} desactivees, "
            f"{len(stats['rising'])} en hausse, {len(stats['declining'])} en baisse"
        )
        return stats

    async def _fetch_and_store_da(self, plateforme: Plateforme) -> bool:
        """Recupere le DA actuel et l'ajoute a l'historique."""
        result = await self.da_fetcher.fetch_da(plateforme.url_base)
        if not result:
            return False

        # Mettre a jour le DA actuel
        plateforme.da_actuel = result["da"]

        # Ajouter a l'historique
        record = PlatformDAHistory(
            plateforme_id=plateforme.id,
            da_value=result["da"],
            source=result["source"],
            measured_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()

        logger.info(f"[{plateforme.slug}] DA: {result['da']} ({result['source']})")
        return True

    def _calculate_da_trend(self, plateforme_id: int) -> float | None:
        """
        Regression lineaire sur l'historique DA (6 derniers mois).
        Retourne la pente (DA points/mois). Positif = en hausse.
        """
        six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
        history = (
            self.db.execute(
                select(PlatformDAHistory)
                .where(
                    PlatformDAHistory.plateforme_id == plateforme_id,
                    PlatformDAHistory.measured_at >= six_months_ago,
                )
                .order_by(PlatformDAHistory.measured_at)
            )
            .scalars()
            .all()
        )

        if len(history) < 2:
            return None

        # X = jours depuis le premier point, Y = DA
        base_time = history[0].measured_at
        x = np.array([(h.measured_at - base_time).days for h in history], dtype=float)
        y = np.array([h.da_value for h in history], dtype=float)

        # Regression lineaire
        if x[-1] - x[0] == 0:
            return 0.0

        coeffs = np.polyfit(x, y, 1)
        slope_per_day = coeffs[0]
        slope_per_month = slope_per_day * 30

        return round(slope_per_month, 2)

    def _build_metrics(self, plateforme: Plateforme, da_trend: float | None) -> PlatformMetrics:
        """Construit les metriques pour le scoring global (pas par projet)."""
        # Taux de survie
        total = (
            self.db.execute(
                select(func.count(Post.id)).where(Post.plateforme_id == plateforme.id)
            ).scalar()
            or 0
        )
        alive = (
            self.db.execute(
                select(func.count(Post.id)).where(
                    Post.plateforme_id == plateforme.id, Post.statut == "publie"
                )
            ).scalar()
            or 0
        )
        taux_survie = alive / total if total > 0 else 1.0

        # Jours depuis dernier post (global, pas par projet)
        last_post = self.db.execute(
            select(Post.publie_at)
            .where(Post.plateforme_id == plateforme.id, Post.publie_at.isnot(None))
            .order_by(Post.publie_at.desc())
            .limit(1)
        ).scalar()
        jours = (datetime.now(timezone.utc) - last_post).days if last_post else 999

        difficulte_map = {"facile": 1.0, "moyen": 0.6, "difficile": 0.3}

        return PlatformMetrics(
            da_actuel=plateforme.da_actuel or 0,
            dofollow=plateforme.dofollow,
            taux_survie=taux_survie,
            traffic_estime=0,
            pertinence_thematique=0.5,  # Score global, pas par projet
            da_tendance=da_trend or 0,
            difficulte=difficulte_map.get(plateforme.difficulte_posting, 0.6),
            jours_depuis_dernier_post=jours,
        )

    def _auto_disable_platforms(self) -> list[str]:
        """Desactive les plateformes avec taux de survie trop bas."""
        disabled = []
        plateformes = (
            self.db.execute(select(Plateforme).where(Plateforme.actif.is_(True)))
            .scalars()
            .all()
        )

        for p in plateformes:
            total = (
                self.db.execute(
                    select(func.count(Post.id)).where(Post.plateforme_id == p.id)
                ).scalar()
                or 0
            )
            if total < MIN_POSTS_FOR_JUDGMENT:
                continue

            dead = (
                self.db.execute(
                    select(func.count(Post.id)).where(
                        Post.plateforme_id == p.id,
                        Post.statut.in_(["supprime", "404"]),
                    )
                ).scalar()
                or 0
            )

            survival = (total - dead) / total
            if survival < AUTO_DISABLE_SURVIVAL_THRESHOLD:
                p.actif = False
                disabled.append(p.slug)
                logger.warning(
                    f"Auto-desactivation: {p.nom} (survie {survival:.0%}, "
                    f"{dead}/{total} morts)"
                )

        if disabled:
            self.db.commit()

        return disabled
