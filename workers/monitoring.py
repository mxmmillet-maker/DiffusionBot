import asyncio
import logging
import random
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import Plateforme, Post
from services.link_checker import LinkChecker
from services.telegram_notifier import TelegramNotifier

logger = logging.getLogger("diffusionbot.worker.monitoring")

# Seuil d'erreurs consecutives avant de marquer un post comme mort
MAX_CONSECUTIVE_ERRORS = 3
# Batch size pour les verifications
BATCH_SIZE = 20


class MonitoringWorker:
    """Worker hebdomadaire de verification des liens."""

    def __init__(
        self,
        db_session: Session,
        link_checker: LinkChecker,
        notifier: TelegramNotifier,
    ):
        self.db = db_session
        self.checker = link_checker
        self.notifier = notifier

    async def run(self) -> dict:
        """Execute le cycle de monitoring. Retourne les stats."""
        stats = {
            "verified": 0,
            "alive": 0,
            "dead": 0,
            "dofollow_changes": 0,
            "newly_dead": [],
            "problematic_platforms": [],
        }

        # Charger tous les posts publies
        posts = (
            self.db.execute(
                select(Post).where(Post.statut == "publie").order_by(Post.derniere_verification)
            )
            .scalars()
            .all()
        )

        if not posts:
            logger.info("Aucun post publie a verifier")
            await self.notifier.send_weekly_monitoring(stats)
            return stats

        logger.info(f"Verification de {len(posts)} liens publies")

        # Traiter par batch
        for i in range(0, len(posts), BATCH_SIZE):
            batch = posts[i : i + BATCH_SIZE]
            await self._verify_batch(batch, stats)

            # Pause entre les batchs (comportement humain)
            if i + BATCH_SIZE < len(posts):
                pause = random.uniform(5, 15)
                logger.info(f"Pause {pause:.0f}s entre les batchs")
                await asyncio.sleep(pause)

        # Calculer les taux de survie par plateforme
        self._update_survival_stats(stats)

        # Rapport
        await self.notifier.send_weekly_monitoring(stats)
        logger.info(
            f"Monitoring termine: {stats['verified']} verifies, "
            f"{stats['alive']} vivants, {stats['dead']} morts, "
            f"{stats['dofollow_changes']} changements dofollow"
        )
        return stats

    async def _verify_batch(self, posts: list[Post], stats: dict):
        """Verifie un batch de posts."""
        urls = []
        for post in posts:
            if not post.url_publie:
                continue
            # Reconstituer l'URL du backlink (sans UTM pour la recherche dans le HTML)
            backlink_url = None
            if post.contenu and post.contenu.url_source:
                backlink_url = post.contenu.url_source
            urls.append((post.url_publie, backlink_url))

        if not urls:
            return

        results = await self.checker.check_batch(urls, concurrency=5)

        for post, result in zip(posts, results):
            if not post.url_publie:
                continue

            stats["verified"] += 1
            post.derniere_verification = datetime.now(timezone.utc)

            if result.alive:
                stats["alive"] += 1
                post.nb_verifications_ok += 1
                post.nb_erreurs_consecutives = 0

                # Verifier changement dofollow
                if result.dofollow is not None and post.dofollow_confirme is not None:
                    if result.dofollow != post.dofollow_confirme:
                        stats["dofollow_changes"] += 1
                        old = "dofollow" if post.dofollow_confirme else "nofollow"
                        new = "dofollow" if result.dofollow else "nofollow"
                        logger.warning(
                            f"Changement {old} -> {new}: {post.url_publie} "
                            f"sur {post.plateforme.nom if post.plateforme else '?'}"
                        )

                if result.dofollow is not None:
                    post.dofollow_confirme = result.dofollow

            else:
                post.nb_erreurs_consecutives += 1
                post.erreur_detail = result.error or f"HTTP {result.http_status}"

                if post.nb_erreurs_consecutives >= MAX_CONSECUTIVE_ERRORS:
                    old_statut = post.statut
                    post.statut = "404" if result.http_status == 404 else "supprime"
                    stats["dead"] += 1
                    stats["newly_dead"].append({
                        "url": post.url_publie,
                        "platform": post.plateforme.nom if post.plateforme else "?",
                        "reason": post.erreur_detail,
                    })
                    logger.warning(
                        f"Lien mort ({post.statut}): {post.url_publie} "
                        f"sur {post.plateforme.nom if post.plateforme else '?'} "
                        f"({post.nb_erreurs_consecutives} erreurs consecutives)"
                    )
                else:
                    logger.info(
                        f"Erreur temporaire ({post.nb_erreurs_consecutives}/{MAX_CONSECUTIVE_ERRORS}): "
                        f"{post.url_publie} - {result.error}"
                    )

        self.db.commit()

    def _update_survival_stats(self, stats: dict):
        """Identifie les plateformes problematiques."""
        plateformes = self.db.execute(
            select(Plateforme).where(Plateforme.actif.is_(True))
        ).scalars().all()

        for p in plateformes:
            total = (
                self.db.execute(
                    select(func.count(Post.id)).where(Post.plateforme_id == p.id)
                ).scalar() or 0
            )
            if total == 0:
                continue

            dead = (
                self.db.execute(
                    select(func.count(Post.id)).where(
                        Post.plateforme_id == p.id,
                        Post.statut.in_(["supprime", "404"]),
                    )
                ).scalar() or 0
            )

            survival_rate = (total - dead) / total
            if survival_rate < 0.5:
                stats["problematic_platforms"].append(
                    f"{p.nom}: {survival_rate:.0%} survie ({dead}/{total} morts)"
                )
                logger.warning(f"Plateforme problematique: {p.nom} ({survival_rate:.0%} survie)")
