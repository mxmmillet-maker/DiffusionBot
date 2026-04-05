import asyncio
import logging
import random
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from adapters.base import AbstractPlatformAdapter
from adapters.registry import get_adapter, load_all_adapters
from db.models import ComptePlateforme, Contenu, Plateforme, Post, Projet
from services.content_reformulator import ContentReformulator
from services.scheduler import HumanScheduler
from services.scoring import PlatformMetrics, PlatformScorer
from services.telegram_notifier import TelegramNotifier
from services.utm_builder import UTMBuilder

logger = logging.getLogger("diffusionbot.worker.diffusion")


class DiffusionWorker:
    """Worker quotidien de diffusion de contenu."""

    def __init__(
        self,
        db_session: Session,
        reformulator: ContentReformulator,
        scorer: PlatformScorer,
        notifier: TelegramNotifier,
        scheduler: HumanScheduler,
        utm_builder: UTMBuilder,
        max_retries: int = 3,
    ):
        self.db = db_session
        self.reformulator = reformulator
        self.scorer = scorer
        self.notifier = notifier
        self.scheduler = scheduler
        self.utm = utm_builder
        self.max_retries = max_retries

    async def run(self) -> dict:
        """Execute le cycle de diffusion. Retourne les stats du run."""
        load_all_adapters()

        stats = {
            "published": 0,
            "failed": 0,
            "skipped": 0,
            "active_projects": 0,
            "per_project": [],
            "errors": [],
        }

        projets = (
            self.db.execute(select(Projet).where(Projet.actif.is_(True))).scalars().all()
        )
        stats["active_projects"] = len(projets)

        for projet in projets:
            project_stats = {"name": projet.nom, "count": 0}
            posts_today = self._count_posts_today(projet.id)
            posts_to_do = self.scheduler.should_post_today(projet.rythme_diffusion_jour)
            remaining = max(0, posts_to_do - posts_today)

            if remaining == 0:
                logger.info(f"[{projet.slug}] Quota atteint ({posts_today}/{posts_to_do})")
                stats["skipped"] += 1
                stats["per_project"].append(project_stats)
                continue

            logger.info(
                f"[{projet.slug}] {remaining} post(s) a faire "
                f"({posts_today} deja faits, quota {posts_to_do})"
            )

            for i in range(remaining):
                if i > 0:
                    # Delai humain entre les posts
                    delay = random.randint(60, 300)  # 1-5 min entre posts du meme run
                    logger.info(f"[{projet.slug}] Pause de {delay}s avant le prochain post")
                    await asyncio.sleep(delay)

                combo = self._select_best_combo(projet)
                if not combo:
                    logger.info(f"[{projet.slug}] Aucun combo contenu/plateforme disponible")
                    break

                contenu, plateforme = combo
                result = await self._publish_one(contenu, plateforme, projet)

                if result:
                    stats["published"] += 1
                    project_stats["count"] += 1
                else:
                    stats["failed"] += 1

            stats["per_project"].append(project_stats)

        # Rapport Telegram
        await self.notifier.send_daily_report(stats)
        logger.info(
            f"Run termine: {stats['published']} publies, "
            f"{stats['failed']} echecs, {stats['skipped']} projets skip"
        )
        return stats

    def _count_posts_today(self, projet_id: int) -> int:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (
            self.db.execute(
                select(func.count(Post.id)).where(
                    Post.projet_id == projet_id,
                    Post.publie_at >= today_start,
                    Post.statut == "publie",
                )
            ).scalar()
            or 0
        )

    def _select_best_combo(self, projet: Projet) -> tuple[Contenu, Plateforme] | None:
        """Selectionne le meilleur contenu + plateforme non encore combines."""
        # Contenus eligibles
        contenus = (
            self.db.execute(
                select(Contenu).where(
                    Contenu.projet_id == projet.id,
                    Contenu.statut.in_(["nouveau", "en_diffusion"]),
                )
            )
            .scalars()
            .all()
        )
        if not contenus:
            return None

        # Plateformes actives
        plateformes = (
            self.db.execute(select(Plateforme).where(Plateforme.actif.is_(True)))
            .scalars()
            .all()
        )
        if not plateformes:
            return None

        # Paires deja publiees
        existing_pairs = set(
            self.db.execute(
                select(Post.contenu_id, Post.plateforme_id).where(
                    Post.projet_id == projet.id,
                    Post.statut.in_(["publie", "planifie"]),
                )
            ).all()
        )

        # Scorer les plateformes
        best_score = -1
        best_combo = None

        for plateforme in plateformes:
            metrics = self._build_metrics(plateforme, projet)
            score = self.scorer.calculate_score(metrics)

            for contenu in contenus:
                if (contenu.id, plateforme.id) in existing_pairs:
                    continue
                if score > best_score:
                    best_score = score
                    best_combo = (contenu, plateforme)

        if best_combo:
            logger.info(
                f"Meilleur combo: '{best_combo[0].titre[:40]}' "
                f"sur {best_combo[1].nom} (score: {best_score})"
            )
        return best_combo

    def _build_metrics(self, plateforme: Plateforme, projet: Projet) -> PlatformMetrics:
        """Construit les metriques pour le scoring."""
        # Taux de survie
        total_posts = (
            self.db.execute(
                select(func.count(Post.id)).where(Post.plateforme_id == plateforme.id)
            ).scalar()
            or 0
        )
        alive_posts = (
            self.db.execute(
                select(func.count(Post.id)).where(
                    Post.plateforme_id == plateforme.id, Post.statut == "publie"
                )
            ).scalar()
            or 0
        )
        taux_survie = alive_posts / total_posts if total_posts > 0 else 1.0

        # Jours depuis le dernier post sur cette plateforme pour ce projet
        last_post = self.db.execute(
            select(Post.publie_at)
            .where(
                Post.plateforme_id == plateforme.id,
                Post.projet_id == projet.id,
                Post.publie_at.isnot(None),
            )
            .order_by(Post.publie_at.desc())
            .limit(1)
        ).scalar()

        if last_post:
            jours = (datetime.now(timezone.utc) - last_post).days
        else:
            jours = 999  # jamais poste = priorite max

        # Pertinence thematique
        pertinence = 0.5  # defaut
        if projet.thematiques and plateforme.thematiques:
            projet_tags = set(projet.thematiques) if isinstance(projet.thematiques, list) else set()
            plat_tags = (
                set(plateforme.thematiques) if isinstance(plateforme.thematiques, list) else set()
            )
            if projet_tags and plat_tags:
                overlap = len(projet_tags & plat_tags)
                pertinence = min(overlap / max(len(projet_tags), 1), 1.0)

        difficulte_map = {"facile": 1.0, "moyen": 0.6, "difficile": 0.3}

        return PlatformMetrics(
            da_actuel=plateforme.da_actuel or 0,
            dofollow=plateforme.dofollow,
            taux_survie=taux_survie,
            traffic_estime=0,  # sera rempli par worker intelligence
            pertinence_thematique=pertinence,
            da_tendance=0,  # sera rempli par worker intelligence
            difficulte=difficulte_map.get(plateforme.difficulte_posting, 0.6),
            jours_depuis_dernier_post=jours,
        )

    async def _publish_one(
        self, contenu: Contenu, plateforme: Plateforme, projet: Projet
    ) -> bool:
        """Reformule et publie un contenu sur une plateforme. Retourne True si succes."""
        # Creer le post en statut planifie
        post = Post(
            contenu_id=contenu.id,
            plateforme_id=plateforme.id,
            projet_id=projet.id,
            statut="planifie",
        )
        self.db.add(post)
        self.db.commit()
        self.db.refresh(post)

        # Generer UTM
        utm_url = self.utm.build(contenu.url_source, plateforme.slug, projet.slug, post.id)
        utm_dict = self.utm.get_utm_dict(plateforme.slug, projet.slug, post.id)
        post.utm_params = utm_dict

        # Charger l'adaptateur
        try:
            adapter_cls = get_adapter(plateforme.slug)
        except KeyError:
            logger.error(f"Adaptateur introuvable: {plateforme.slug}")
            post.statut = "erreur"
            post.erreur_detail = f"Adaptateur introuvable: {plateforme.slug}"
            self.db.commit()
            return False

        adapter: AbstractPlatformAdapter = adapter_cls()

        # Authentification
        compte = self.db.execute(
            select(ComptePlateforme).where(
                ComptePlateforme.plateforme_id == plateforme.id,
                ComptePlateforme.actif.is_(True),
            )
        ).scalar_one_or_none()

        if not compte:
            logger.error(f"Pas de compte actif pour {plateforme.nom}")
            post.statut = "erreur"
            post.erreur_detail = "Pas de compte actif"
            self.db.commit()
            return False

        try:
            auth_ok = await adapter.authenticate(compte)
            if not auth_ok:
                post.statut = "erreur"
                post.erreur_detail = "Authentification echouee"
                self.db.commit()
                return False
        except Exception as e:
            logger.error(f"Erreur auth {plateforme.nom}: {e}")
            post.statut = "erreur"
            post.erreur_detail = f"Erreur auth: {e}"
            self.db.commit()
            return False

        # Reformuler le contenu
        try:
            constraints = adapter.get_constraints()
            reformulated = self.reformulator.reformulate(
                original_title=contenu.titre,
                original_body=contenu.contenu_brut or "",
                target_url=utm_url,
                keywords=contenu.mots_cles or [],
                constraints=constraints,
                content_type=adapter.content_type,
                platform_name=plateforme.nom,
            )
            post.titre_adapte = reformulated["title"]
            post.contenu_adapte = reformulated["body"]
        except Exception as e:
            logger.error(f"Erreur reformulation pour {plateforme.nom}: {e}")
            post.statut = "erreur"
            post.erreur_detail = f"Erreur reformulation: {e}"
            self.db.commit()
            await adapter.cleanup()
            return False

        # Publier avec retry
        for attempt in range(1, self.max_retries + 1):
            post.tentatives = attempt
            try:
                # Pause humaine avant publication
                await asyncio.sleep(random.uniform(2, 8))

                result = await adapter.publish(
                    title=reformulated["title"],
                    body=reformulated["body"],
                    tags=reformulated.get("tags", []),
                    target_url=utm_url,
                )

                if result.success:
                    post.statut = "publie"
                    post.url_publie = result.url
                    post.dofollow_confirme = result.dofollow_detected
                    post.publie_at = datetime.now(timezone.utc)
                    self.db.commit()

                    # Mettre a jour le statut du contenu
                    if contenu.statut == "nouveau":
                        contenu.statut = "en_diffusion"
                        self.db.commit()

                    logger.info(
                        f"PUBLIE: '{reformulated['title'][:50]}' sur {plateforme.nom} -> {result.url}"
                    )
                    await adapter.cleanup()
                    return True

                logger.warning(
                    f"Tentative {attempt}/{self.max_retries} echouee sur {plateforme.nom}: "
                    f"{result.error_message}"
                )
                post.erreur_detail = result.error_message

                if attempt < self.max_retries:
                    backoff = 60 * (2 ** (attempt - 1)) + random.randint(0, 30)
                    await asyncio.sleep(backoff)

            except Exception as e:
                logger.error(f"Erreur publication tentative {attempt}: {e}")
                post.erreur_detail = str(e)
                if attempt < self.max_retries:
                    await asyncio.sleep(60 * attempt)

        post.statut = "erreur"
        self.db.commit()
        await adapter.cleanup()
        logger.error(f"ECHEC apres {self.max_retries} tentatives sur {plateforme.nom}")
        return False
