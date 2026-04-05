from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ContentType(Enum):
    ARTICLE = "article"
    SHORT_POST = "post_court"
    COMMENT = "commentaire"
    PROFILE_BIO = "profil"
    WIKI = "wiki"


@dataclass
class PostResult:
    success: bool
    url: Optional[str] = None
    error_message: Optional[str] = None
    dofollow_detected: Optional[bool] = None
    raw_response: Optional[dict] = None


@dataclass
class VerifyResult:
    alive: bool
    dofollow: Optional[bool] = None
    http_status: Optional[int] = None
    error_message: Optional[str] = None


@dataclass
class PlatformConstraints:
    max_title_length: int
    max_body_length: int
    supports_html: bool
    supports_markdown: bool
    supports_images: bool
    required_fields: list[str] = field(default_factory=lambda: ["title", "body"])
    max_tags: int = 5
    max_links_in_body: int = 3


class AbstractPlatformAdapter(ABC):
    """Classe de base pour tous les adaptateurs de plateforme."""

    slug: str
    name: str
    content_type: ContentType

    @abstractmethod
    def get_constraints(self) -> PlatformConstraints:
        ...

    @abstractmethod
    async def authenticate(self, compte) -> bool:
        """Authentification sur la plateforme. Retourne True si succes."""
        ...

    @abstractmethod
    async def publish(
        self,
        title: str,
        body: str,
        tags: list[str],
        target_url: str,
        images: list[str] | None = None,
    ) -> PostResult:
        """Publie le contenu adapte. Retourne le resultat avec l'URL."""
        ...

    @abstractmethod
    async def verify(self, published_url: str) -> VerifyResult:
        """Verifie qu'un post est toujours en ligne et son statut dofollow."""
        ...

    async def cleanup(self) -> None:
        """Nettoyage (fermer navigateur, session, etc.)."""
        pass
