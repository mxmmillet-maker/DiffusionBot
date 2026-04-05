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

logger = logging.getLogger("diffusionbot.adapters.medium")


@register
class MediumAdapter(APIPosterMixin, AbstractPlatformAdapter):
    slug = "medium"
    name = "Medium"
    content_type = ContentType.ARTICLE

    API_BASE = "https://api.medium.com/v1"

    def __init__(self):
        self._token: str | None = None
        self._user_id: str | None = None

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=100,
            max_body_length=50_000,
            supports_html=True,
            supports_markdown=True,
            supports_images=True,
            required_fields=["title", "body"],
            max_tags=5,
            max_links_in_body=10,
        )

    async def authenticate(self, compte) -> bool:
        self._token = compte.token_api
        if not self._token:
            logger.error("Medium: pas de token API")
            return False
        try:
            resp = await self._get(f"{self.API_BASE}/me", token=self._token)
            if resp.status_code == 200:
                self._user_id = resp.json()["data"]["id"]
                logger.info(f"Medium: authentifie en tant que {self._user_id}")
                return True
            logger.error(f"Medium: auth echouee ({resp.status_code})")
            return False
        except Exception as e:
            logger.error(f"Medium: erreur auth: {e}")
            return False

    async def publish(
        self,
        title: str,
        body: str,
        tags: list[str],
        target_url: str,
        images: list[str] | None = None,
    ) -> PostResult:
        if not self._user_id or not self._token:
            return PostResult(success=False, error_message="Non authentifie")

        payload = {
            "title": title,
            "contentFormat": "html",
            "content": body,
            "tags": tags[:5],
            "publishStatus": "public",
        }

        try:
            resp = await self._post(
                f"{self.API_BASE}/users/{self._user_id}/posts",
                json=payload,
                token=self._token,
            )
            if resp.status_code == 201:
                data = resp.json()["data"]
                url = data.get("url", "")
                logger.info(f"Medium: publie avec succes -> {url}")
                return PostResult(success=True, url=url, raw_response=data)

            logger.error(f"Medium: publication echouee ({resp.status_code}): {resp.text}")
            return PostResult(success=False, error_message=f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Medium: erreur publication: {e}")
            return PostResult(success=False, error_message=str(e))

    async def verify(self, published_url: str) -> VerifyResult:
        try:
            resp = await self._get(published_url)
            if resp.status_code == 200:
                dofollow = 'rel="nofollow"' not in resp.text
                return VerifyResult(alive=True, dofollow=dofollow, http_status=200)
            return VerifyResult(
                alive=resp.status_code != 404,
                http_status=resp.status_code,
                error_message=f"HTTP {resp.status_code}",
            )
        except Exception as e:
            return VerifyResult(alive=False, error_message=str(e))
