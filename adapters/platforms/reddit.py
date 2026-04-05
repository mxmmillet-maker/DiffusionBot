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

logger = logging.getLogger("diffusionbot.adapters.reddit")


@register
class RedditAdapter(APIPosterMixin, AbstractPlatformAdapter):
    """Reddit — OAuth2 API. Attention: rythme tres lent, anti-spam agressif."""

    slug = "reddit"
    name = "Reddit"
    content_type = ContentType.SHORT_POST

    API_BASE = "https://oauth.reddit.com"
    AUTH_URL = "https://www.reddit.com/api/v1/access_token"

    def __init__(self):
        self._access_token: str | None = None
        self._subreddit: str = ""

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=300,
            max_body_length=40_000,
            supports_html=False,
            supports_markdown=True,
            supports_images=False,
            required_fields=["title", "body"],
            max_tags=0,  # Reddit utilise des flairs, pas des tags
            max_links_in_body=3,  # Reddit n'aime pas trop les liens
        )

    async def authenticate(self, compte) -> bool:
        # Reddit OAuth2: token_api = refresh_token, identifiant = "client_id:client_secret"
        if not compte.token_api or not compte.identifiant:
            return False

        try:
            parts = compte.identifiant.split(":")
            if len(parts) != 2:
                logger.error("Reddit: format identifiant invalide (attendu client_id:client_secret)")
                return False

            client_id, client_secret = parts
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.AUTH_URL,
                    auth=(client_id, client_secret),
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": compte.token_api,
                    },
                    headers={"User-Agent": "DiffusionBot/1.0"},
                )

            if resp.status_code == 200:
                self._access_token = resp.json()["access_token"]
                logger.info("Reddit: authentifie via OAuth2")
                return True
            logger.error(f"Reddit: auth echouee ({resp.status_code})")
            return False
        except Exception as e:
            logger.error(f"Reddit auth error: {e}")
            return False

    async def publish(self, title, body, tags, target_url, images=None) -> PostResult:
        if not self._access_token:
            return PostResult(success=False, error_message="Non authentifie")

        # Determiner le subreddit (stocke dans les notes ou tags)
        subreddit = self._subreddit or "selfpublish"

        payload = {
            "sr": subreddit,
            "kind": "self",
            "title": title,
            "text": body,
            "resubmit": True,
        }

        try:
            resp = await self._post(
                f"{self.API_BASE}/api/submit",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "User-Agent": "DiffusionBot/1.0",
                },
            )
            data = resp.json()

            if resp.status_code == 200 and not data.get("json", {}).get("errors"):
                url = data.get("json", {}).get("data", {}).get("url", "")
                logger.info(f"Reddit: publie -> {url}")
                return PostResult(success=True, url=url, raw_response=data)

            errors = data.get("json", {}).get("errors", [])
            err_msg = str(errors[0]) if errors else f"HTTP {resp.status_code}"
            return PostResult(success=False, error_message=err_msg)
        except Exception as e:
            return PostResult(success=False, error_message=str(e))

    async def verify(self, published_url: str) -> VerifyResult:
        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=20, follow_redirects=True,
                headers={"User-Agent": "DiffusionBot/1.0"},
            ) as client:
                resp = await client.get(published_url)
            if resp.status_code == 200:
                # Reddit links sont generalement nofollow
                return VerifyResult(alive=True, dofollow=False, http_status=200)
            return VerifyResult(alive=resp.status_code != 404, http_status=resp.status_code)
        except Exception as e:
            return VerifyResult(alive=False, error_message=str(e))
