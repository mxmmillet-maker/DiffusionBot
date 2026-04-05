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

logger = logging.getLogger("diffusionbot.adapters.blogger")


@register
class BloggerAdapter(APIPosterMixin, AbstractPlatformAdapter):
    """Blogger/Blogspot — Google Blogger API v3."""

    slug = "blogger"
    name = "Blogger"
    content_type = ContentType.ARTICLE

    API_BASE = "https://www.googleapis.com/blogger/v3"

    def __init__(self):
        self._token: str | None = None
        self._blog_id: str | None = None

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=500,
            max_body_length=500_000,
            supports_html=True,
            supports_markdown=False,
            supports_images=True,
            required_fields=["title", "body"],
            max_tags=20,
            max_links_in_body=50,
        )

    async def authenticate(self, compte) -> bool:
        self._token = compte.token_api  # OAuth2 token Google
        self._blog_id = compte.identifiant  # Blog ID
        if not self._token or not self._blog_id:
            return False
        try:
            resp = await self._get(
                f"{self.API_BASE}/blogs/{self._blog_id}",
                token=self._token,
            )
            if resp.status_code == 200:
                blog_name = resp.json().get("name", "?")
                logger.info(f"Blogger: authentifie (blog: {blog_name})")
                return True
            logger.error(f"Blogger: auth echouee ({resp.status_code})")
            return False
        except Exception as e:
            logger.error(f"Blogger auth error: {e}")
            return False

    async def publish(self, title, body, tags, target_url, images=None) -> PostResult:
        payload = {
            "kind": "blogger#post",
            "title": title,
            "content": body,
        }
        if tags:
            payload["labels"] = tags[:20]

        try:
            resp = await self._post(
                f"{self.API_BASE}/blogs/{self._blog_id}/posts",
                json=payload,
                token=self._token,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                url = data.get("url", "")
                logger.info(f"Blogger: publie -> {url}")
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
