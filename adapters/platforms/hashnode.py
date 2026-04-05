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

logger = logging.getLogger("diffusionbot.adapters.hashnode")


@register
class HashnodeAdapter(APIPosterMixin, AbstractPlatformAdapter):
    """Hashnode — GraphQL API."""

    slug = "hashnode"
    name = "Hashnode"
    content_type = ContentType.ARTICLE

    API_BASE = "https://gql.hashnode.com"

    def __init__(self):
        self._token: str | None = None
        self._publication_id: str | None = None

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=150,
            max_body_length=100_000,
            supports_html=False,
            supports_markdown=True,
            supports_images=True,
            required_fields=["title", "body"],
            max_tags=5,
            max_links_in_body=20,
        )

    async def authenticate(self, compte) -> bool:
        self._token = compte.token_api
        # publication_id stocke dans le champ identifiant du compte
        self._publication_id = compte.identifiant
        if not self._token or not self._publication_id:
            return False
        try:
            query = '{ me { id username } }'
            resp = await self._post(
                self.API_BASE,
                json={"query": query},
                headers={"Authorization": self._token},
            )
            data = resp.json()
            if data.get("data", {}).get("me"):
                logger.info(f"Hashnode: authentifie ({data['data']['me']['username']})")
                return True
            return False
        except Exception as e:
            logger.error(f"Hashnode auth error: {e}")
            return False

    async def publish(self, title, body, tags, target_url, images=None) -> PostResult:
        mutation = """
        mutation PublishPost($input: PublishPostInput!) {
            publishPost(input: $input) {
                post { id url title }
            }
        }
        """
        tag_objects = [{"slug": t.lower().replace(" ", "-"), "name": t} for t in tags[:5]]
        variables = {
            "input": {
                "title": title,
                "contentMarkdown": body,
                "publicationId": self._publication_id,
                "tags": tag_objects,
            }
        }
        try:
            resp = await self._post(
                self.API_BASE,
                json={"query": mutation, "variables": variables},
                headers={"Authorization": self._token},
            )
            data = resp.json()
            post_data = data.get("data", {}).get("publishPost", {}).get("post")
            if post_data:
                url = post_data.get("url", "")
                logger.info(f"Hashnode: publie -> {url}")
                return PostResult(success=True, url=url, raw_response=post_data)
            errors = data.get("errors", [])
            err_msg = errors[0]["message"] if errors else "Unknown error"
            return PostResult(success=False, error_message=err_msg)
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
