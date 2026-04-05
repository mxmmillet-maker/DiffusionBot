from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Projet(Base):
    __tablename__ = "projets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    domaine: Mapped[str] = mapped_column(String(200), nullable=False)
    url_base: Mapped[str] = mapped_column(String(500), nullable=False)
    thematiques: Mapped[dict | None] = mapped_column(JSON, default=list)
    rythme_diffusion_jour: Mapped[int] = mapped_column(Integer, default=2)
    ga4_property_id: Mapped[str | None] = mapped_column(String(50))
    gsc_site_url: Mapped[str | None] = mapped_column(String(500))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    contenus: Mapped[list["Contenu"]] = relationship(back_populates="projet")
    posts: Mapped[list["Post"]] = relationship(back_populates="projet")
    project_da_history: Mapped[list["ProjectDAHistory"]] = relationship(back_populates="projet")


class Plateforme(Base):
    __tablename__ = "plateformes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(200), nullable=False)
    url_base: Mapped[str] = mapped_column(String(500), nullable=False)
    type_contenu: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # article, post_court, commentaire, profil, wiki
    adapter_class: Mapped[str] = mapped_column(String(200), nullable=False)
    da_actuel: Mapped[float | None] = mapped_column(Float)
    dofollow: Mapped[bool] = mapped_column(Boolean, default=True)
    inscription_requise: Mapped[bool] = mapped_column(Boolean, default=True)
    difficulte_posting: Mapped[str] = mapped_column(
        String(20), default="moyen"
    )  # facile, moyen, difficile
    thematiques: Mapped[dict | None] = mapped_column(JSON, default=list)
    score_composite: Mapped[float | None] = mapped_column(Float)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    posts: Mapped[list["Post"]] = relationship(back_populates="plateforme")
    comptes: Mapped[list["ComptePlateforme"]] = relationship(back_populates="plateforme")
    da_history: Mapped[list["PlatformDAHistory"]] = relationship(back_populates="plateforme")


class Contenu(Base):
    __tablename__ = "contenus"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id"), nullable=False)
    titre: Mapped[str] = mapped_column(String(500), nullable=False)
    url_source: Mapped[str] = mapped_column(String(1000), nullable=False)
    contenu_brut: Mapped[str | None] = mapped_column(Text)
    mots_cles: Mapped[dict | None] = mapped_column(JSON, default=list)
    categorie: Mapped[str | None] = mapped_column(String(100))
    statut: Mapped[str] = mapped_column(
        String(20), default="nouveau"
    )  # nouveau, en_diffusion, diffuse, archive
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projet: Mapped["Projet"] = relationship(back_populates="contenus")
    posts: Mapped[list["Post"]] = relationship(back_populates="contenu")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contenu_id: Mapped[int] = mapped_column(ForeignKey("contenus.id"), nullable=False)
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id"), nullable=False)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id"), nullable=False)
    url_publie: Mapped[str | None] = mapped_column(String(1000))
    utm_params: Mapped[dict | None] = mapped_column(JSON)
    titre_adapte: Mapped[str | None] = mapped_column(String(500))
    contenu_adapte: Mapped[str | None] = mapped_column(Text)
    statut: Mapped[str] = mapped_column(
        String(20), default="planifie"
    )  # planifie, publie, erreur, supprime, 404
    dofollow_confirme: Mapped[bool | None] = mapped_column(Boolean)
    derniere_verification: Mapped[datetime | None] = mapped_column(DateTime)
    nb_verifications_ok: Mapped[int] = mapped_column(Integer, default=0)
    nb_erreurs_consecutives: Mapped[int] = mapped_column(Integer, default=0)
    erreur_detail: Mapped[str | None] = mapped_column(Text)
    tentatives: Mapped[int] = mapped_column(Integer, default=0)
    publie_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    contenu: Mapped["Contenu"] = relationship(back_populates="posts")
    plateforme: Mapped["Plateforme"] = relationship(back_populates="posts")
    projet: Mapped["Projet"] = relationship(back_populates="posts")
    analytics_traffic: Mapped[list["AnalyticsTraffic"]] = relationship(back_populates="post")


class ComptePlateforme(Base):
    __tablename__ = "comptes_plateforme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id"), nullable=False)
    projet_id: Mapped[int | None] = mapped_column(ForeignKey("projets.id"))
    identifiant: Mapped[str] = mapped_column(String(200), nullable=False)
    mot_de_passe_chiffre: Mapped[str | None] = mapped_column(String(500))
    cookies_session: Mapped[str | None] = mapped_column(Text)
    token_api: Mapped[str | None] = mapped_column(String(500))
    actif: Mapped[bool] = mapped_column(Boolean, default=True)
    dernier_login: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    plateforme: Mapped["Plateforme"] = relationship(back_populates="comptes")


class PlatformDAHistory(Base):
    __tablename__ = "platform_da_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id"), nullable=False)
    da_value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # moz, majestic, ahrefs
    measured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    plateforme: Mapped["Plateforme"] = relationship(back_populates="da_history")


class AnalyticsTraffic(Base):
    __tablename__ = "analytics_traffic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), nullable=False)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id"), nullable=False)
    plateforme_id: Mapped[int] = mapped_column(ForeignKey("plateformes.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    users: Mapped[int] = mapped_column(Integer, default=0)
    bounce_rate: Mapped[float | None] = mapped_column(Float)
    avg_session_duration: Mapped[float | None] = mapped_column(Float)
    conversions: Mapped[int] = mapped_column(Integer, default=0)

    post: Mapped["Post"] = relationship(back_populates="analytics_traffic")


class AnalyticsSEO(Base):
    __tablename__ = "analytics_seo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id"), nullable=False)
    page_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    avg_position: Mapped[float | None] = mapped_column(Float)
    keywords_top10: Mapped[int] = mapped_column(Integer, default=0)
    keywords_top30: Mapped[int] = mapped_column(Integer, default=0)


class ProjectDAHistory(Base):
    __tablename__ = "project_da_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    projet_id: Mapped[int] = mapped_column(ForeignKey("projets.id"), nullable=False)
    da_value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    projet: Mapped["Projet"] = relationship(back_populates="project_da_history")
