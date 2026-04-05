import asyncio
import random

from playwright.async_api import Browser, Page, async_playwright


class BrowserPosterMixin:
    """Mixin pour les plateformes qui necessitent Playwright."""

    _browser: Browser | None = None
    _page: Page | None = None
    _pw = None

    async def _init_browser(self, headless: bool = True) -> Page:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=headless)
        context = await self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="fr-FR",
        )
        self._page = await context.new_page()
        return self._page

    async def _human_type(self, selector: str, text: str):
        """Frappe au clavier avec delai humain variable."""
        for char in text:
            await self._page.type(selector, char, delay=random.randint(50, 150))

    async def _random_pause(self, min_s: float = 0.5, max_s: float = 3.0):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _click_and_wait(self, selector: str, wait_after: float = 1.0):
        await self._page.click(selector)
        await asyncio.sleep(wait_after + random.uniform(0, 1))

    async def cleanup(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()
