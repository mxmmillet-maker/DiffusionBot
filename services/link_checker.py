import logging
import re

import httpx

logger = logging.getLogger("diffusionbot.link_checker")


class LinkCheckResult:
    __slots__ = ("alive", "http_status", "dofollow", "redirect_url", "error")

    def __init__(
        self,
        alive: bool,
        http_status: int | None = None,
        dofollow: bool | None = None,
        redirect_url: str | None = None,
        error: str | None = None,
    ):
        self.alive = alive
        self.http_status = http_status
        self.dofollow = dofollow
        self.redirect_url = redirect_url
        self.error = error


class LinkChecker:
    """Verifie qu'un lien est en ligne et detecte dofollow/nofollow."""

    # Pattern pour detecter les liens nofollow
    NOFOLLOW_PATTERNS = [
        re.compile(r'rel\s*=\s*"[^"]*nofollow[^"]*"', re.IGNORECASE),
        re.compile(r"rel\s*=\s*'[^']*nofollow[^']*'", re.IGNORECASE),
    ]

    def __init__(self, timeout: float = 20.0, max_redirects: int = 5):
        self.timeout = timeout
        self.max_redirects = max_redirects

    async def check(self, url: str, backlink_url: str | None = None) -> LinkCheckResult:
        """
        Verifie une URL.
        - url: URL du post publie
        - backlink_url: URL du backlink a chercher dans la page (optionnel)

        Retourne alive, http_status, dofollow.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=self.max_redirects,
            ) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                    },
                )

            if resp.status_code == 404:
                return LinkCheckResult(alive=False, http_status=404)

            if resp.status_code >= 400:
                return LinkCheckResult(
                    alive=False,
                    http_status=resp.status_code,
                    error=f"HTTP {resp.status_code}",
                )

            # Detecter redirect
            redirect_url = None
            if resp.url and str(resp.url) != url:
                redirect_url = str(resp.url)

            # Analyser dofollow si on a le contenu HTML
            dofollow = None
            if backlink_url and resp.status_code == 200:
                dofollow = self._check_dofollow(resp.text, backlink_url)

            return LinkCheckResult(
                alive=True,
                http_status=resp.status_code,
                dofollow=dofollow,
                redirect_url=redirect_url,
            )

        except httpx.TimeoutException:
            return LinkCheckResult(alive=False, error="Timeout")
        except httpx.ConnectError:
            return LinkCheckResult(alive=False, error="Connection error")
        except Exception as e:
            logger.error(f"Erreur check {url}: {e}")
            return LinkCheckResult(alive=False, error=str(e))

    def _check_dofollow(self, html: str, backlink_url: str) -> bool | None:
        """
        Cherche le backlink dans le HTML et verifie s'il est dofollow.
        Retourne True (dofollow), False (nofollow), None (lien introuvable).
        """
        # Chercher les balises <a> contenant l'URL du backlink
        # On cherche avec et sans trailing slash, avec et sans UTM
        base_url = backlink_url.split("?")[0].rstrip("/")
        link_pattern = re.compile(
            rf'<a\s[^>]*href\s*=\s*["\'][^"\']*{re.escape(base_url)}[^"\']*["\'][^>]*>',
            re.IGNORECASE,
        )

        match = link_pattern.search(html)
        if not match:
            return None  # Lien introuvable dans la page

        link_tag = match.group(0)

        # Verifier si le lien a rel="nofollow"
        for pattern in self.NOFOLLOW_PATTERNS:
            if pattern.search(link_tag):
                return False  # nofollow

        return True  # dofollow (pas de rel="nofollow" trouve)

    async def check_batch(
        self, urls: list[tuple[str, str | None]], concurrency: int = 5
    ) -> list[LinkCheckResult]:
        """
        Verifie un batch d'URLs avec concurrence limitee.
        urls: liste de (post_url, backlink_url)
        """
        import asyncio

        semaphore = asyncio.Semaphore(concurrency)
        results = []

        async def _check_one(url: str, backlink: str | None):
            async with semaphore:
                return await self.check(url, backlink)

        tasks = [_check_one(url, bl) for url, bl in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if isinstance(r, LinkCheckResult)
            else LinkCheckResult(alive=False, error=str(r))
            for r in results
        ]
