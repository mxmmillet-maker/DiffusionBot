import logging

from adapters.base import (
    AbstractPlatformAdapter,
    ContentType,
    PlatformConstraints,
    PostResult,
    VerifyResult,
)
from adapters.mixins.browser_poster import BrowserPosterMixin
from adapters.registry import register

logger = logging.getLogger("diffusionbot.adapters.wordpress_com")


@register
class WordPressComAdapter(BrowserPosterMixin, AbstractPlatformAdapter):
    """WordPress.com — Publication via Playwright (interface web)."""

    slug = "wordpress_com"
    name = "WordPress.com"
    content_type = ContentType.ARTICLE

    def __init__(self):
        self._site_url: str | None = None

    def get_constraints(self) -> PlatformConstraints:
        return PlatformConstraints(
            max_title_length=200,
            max_body_length=100_000,
            supports_html=True,
            supports_markdown=False,
            supports_images=True,
            required_fields=["title", "body"],
            max_tags=15,
            max_links_in_body=30,
        )

    async def authenticate(self, compte) -> bool:
        self._site_url = compte.identifiant  # ex: monblog.wordpress.com
        try:
            page = await self._init_browser(headless=True)

            # Si on a des cookies de session, les restaurer
            if compte.cookies_session:
                import json
                cookies = json.loads(compte.cookies_session)
                await page.context.add_cookies(cookies)
                await page.goto(f"https://wordpress.com/home/{self._site_url}")
                await self._random_pause(2, 4)

                # Verifier si on est connecte
                if "log-in" not in page.url:
                    logger.info(f"WordPress.com: connecte via cookies ({self._site_url})")
                    return True

            # Login avec identifiants
            await page.goto("https://wordpress.com/log-in")
            await self._random_pause(1, 3)
            await self._human_type('input[name="usernameOrEmail"]', compte.identifiant)
            await self._click_and_wait('button[type="submit"]', 2)

            # Mot de passe
            if compte.mot_de_passe_chiffre:
                from cryptography.fernet import Fernet
                from config.settings import Settings
                settings = Settings()
                f = Fernet(settings.fernet_key.encode())
                password = f.decrypt(compte.mot_de_passe_chiffre.encode()).decode()
                await self._human_type('input[name="password"]', password)
                await self._click_and_wait('button[type="submit"]', 3)

            if "log-in" not in page.url:
                logger.info(f"WordPress.com: login reussi ({self._site_url})")
                return True

            logger.error("WordPress.com: login echoue")
            return False

        except Exception as e:
            logger.error(f"WordPress.com auth error: {e}")
            return False

    async def publish(self, title, body, tags, target_url, images=None) -> PostResult:
        try:
            page = self._page
            await page.goto(f"https://wordpress.com/post/{self._site_url}")
            await self._random_pause(3, 5)

            # Titre
            title_sel = '.editor-post-title__input, [aria-label="Add title"]'
            await page.wait_for_selector(title_sel, timeout=10000)
            await page.click(title_sel)
            await self._human_type(title_sel, title)
            await self._random_pause(1, 2)

            # Corps - utiliser le block editor
            body_sel = '.block-editor-rich-text__editable, [aria-label="Add default block"]'
            await page.click(body_sel)
            await self._random_pause(0.5, 1.5)

            # Coller le HTML via clipboard
            await page.evaluate(f"""
                const block = document.querySelector('{body_sel}');
                if (block) {{
                    block.innerHTML = `{body.replace('`', '\\`')}`;
                    block.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            """)
            await self._random_pause(2, 4)

            # Publier
            publish_btn = 'button:has-text("Publish"), button:has-text("Publier")'
            await page.click(publish_btn)
            await self._random_pause(2, 3)

            # Confirmer la publication
            confirm_btn = '.editor-post-publish-button, button:has-text("Publish"):visible'
            try:
                await page.click(confirm_btn, timeout=5000)
                await self._random_pause(3, 5)
            except Exception:
                pass  # Peut ne pas avoir de confirmation

            # Recuperer l'URL publiee
            url = page.url
            if "/post/" not in url:
                logger.info(f"WordPress.com: publie -> {url}")
                return PostResult(success=True, url=url)

            # Chercher le lien dans la notification de succes
            try:
                link = await page.wait_for_selector('a:has-text("View Post"), a:has-text("Voir")', timeout=5000)
                url = await link.get_attribute("href")
                logger.info(f"WordPress.com: publie -> {url}")
                return PostResult(success=True, url=url)
            except Exception:
                return PostResult(success=True, url=page.url)

        except Exception as e:
            logger.error(f"WordPress.com publish error: {e}")
            return PostResult(success=False, error_message=str(e))

    async def verify(self, published_url: str) -> VerifyResult:
        try:
            # Verification simple via HTTP (pas besoin de Playwright)
            import httpx
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(published_url)
            if resp.status_code == 200:
                dofollow = 'rel="nofollow"' not in resp.text
                return VerifyResult(alive=True, dofollow=dofollow, http_status=200)
            return VerifyResult(alive=resp.status_code != 404, http_status=resp.status_code)
        except Exception as e:
            return VerifyResult(alive=False, error_message=str(e))
