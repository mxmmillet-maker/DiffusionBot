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

logger = logging.getLogger("diffusionbot.adapters.devto")


@register
class DevToAdapter(APIPosterMixin, AbstractPlatformAdapter):
    """DEV.to — API REST officielle (api.forem.com)."""

    slug = "devto"
    name = "DEV.to"
    content_type = ContentType.ARTICLE

    API_BASE = "https://dev.to/api"

    def __init__(self):
        self._api_key: str | None = None

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=128,
            max_body_length=65_535,
            supports_html=False,
            supports_markdown=True,
            supports_images=True,
            required_fields=["title", "body"],
            max_tags=4,
            max_links_in_body=20,
        )

    async def authenticate(self, compte) -> bool:
        self._api_key = compte.token_api
        if not self._api_key:
            return False
        try:
            resp = await self._get(
                f"{self.API_BASE}/users/me",
                headers={"api-key": self._api_key},
            )
            if resp.status_code == 200:
                logger.info(f"DEV.to: authentifie ({resp.json().get('username', '?')})")
                return True
            return False
        except Exception as e:
            logger.error(f"DEV.to auth error: {e}")
            return False

    async def publish(self, title, body, tags, target_url, images=None) -> PostResult:
        payload = {
            "article": {
                "title": title,
                "body_markdown": body,
                "published": True,
                "tags": [t.lower().replace(" ", "") for t in tags[:4]],
            }
        }
        try:
            resp = await self._post(
                f"{self.API_BASE}/articles",
                json=payload,
                headers={"api-key": self._api_key},
            )
            if resp.status_code == 201:
                data = resp.json()
                url = data.get("url", "")
                logger.info(f"DEV.to: publie -> {url}")
                return PostResult(success=True, url=url, raw_response=data)
            return PostResult(success=False, error_message=f"HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return PostResult(success=False, error_message=str(e))

    async def verify(self, published_url: str) -> VerifyResult:
        try:
            resp = await self._get(published_url)
            if resp.status_code == 200:
                dofollow = 'rel="nofollow"' not in resp.text
                return VerifyResult(alive=True, dofollow=dofollow, http_status=200)
            return VerifyResult(alive=resp.status_code != 404, http_status=resp.status_code)
        except Exception as e:
            return VerifyResult(alive=False, error_message=str(e))
