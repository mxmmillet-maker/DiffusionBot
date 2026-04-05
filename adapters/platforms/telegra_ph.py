import logging

from adapters.base import (
    AbstractPlatformAdapter,
    ContentType,
    PlatformConstraints,
    PostResult,
    VerifyResult,
)
from adapters.mixins.api_poster import APIPosterMixin
from adapters.registry import register

logger = logging.getLogger("diffusionbot.adapters.telegraph")


@register
class TelegraphAdapter(APIPosterMixin, AbstractPlatformAdapter):
    """Telegra.ph — API REST simple, pas d'inscription requise."""

    slug = "telegraph"
    name = "Telegraph"
    content_type = ContentType.ARTICLE

    API_BASE = "https://api.telegra.ph"

    def __init__(self):
        self._access_token: str | None = None
        self._author_name: str = "DiffusionBot"

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=256,
            max_body_length=64_000,
            supports_html=True,
            supports_markdown=False,
            supports_images=True,
            required_fields=["title", "body"],
            max_tags=0,  # Pas de tags sur Telegraph
            max_links_in_body=50,
        )

    async def authenticate(self, compte) -> bool:
        self._access_token = compte.token_api
        if self._access_token:
            # Verifier le token existant
            resp = await self._get(
                f"{self.API_BASE}/getAccountInfo",
                params={"access_token": self._access_token},
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Telegraph: token valide")
                return True

        # Creer un nouveau compte si pas de token
        author_name = compte.identifiant or "DiffusionBot"
        resp = await self._get(
            f"{self.API_BASE}/createAccount",
            params={"short_name": author_name, "author_name": author_name},
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            self._access_token = resp.json()["result"]["access_token"]
            self._author_name = author_name
            logger.info(f"Telegraph: nouveau compte cree ({author_name})")
            return True
        return False

    async def publish(self, title, body, tags, target_url, images=None) -> PostResult:
        # Telegraph attend un tableau de Node objects
        # Simplification: on envoie le HTML dans un seul node
        content = [{"tag": "p", "children": [body]}]

        try:
            resp = await self._post(
                f"{self.API_BASE}/createPage",
                json={
                    "access_token": self._access_token,
                    "title": title,
                    "author_name": self._author_name,
                    "content": content,
                    "return_content": False,
                },
            )
            data = resp.json()
            if data.get("ok"):
                url = data["result"].get("url", "")
                logger.info(f"Telegraph: publie -> {url}")
                return PostResult(success=True, url=url, raw_response=data["result"])
            return PostResult(success=False, error_message=data.get("error", "Unknown"))
        except Exception as e:
            return PostResult(success=False, error_message=str(e))

    async def verify(self, published_url: str) -> VerifyResult:
        try:
            resp = await self._get(published_url)
            if resp.status_code == 200:
                return VerifyResult(alive=True, dofollow=True, http_status=200)
            return VerifyResult(alive=False, http_status=resp.status_code)
        except Exception as e:
            return VerifyResult(alive=False, error_message=str(e))
