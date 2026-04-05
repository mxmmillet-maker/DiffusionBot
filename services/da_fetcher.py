"""
Moz Links API (free tier: 10 requetes/mois sur le plan gratuit, plus avec Moz API).
Recupere le Domain Authority pour les plateformes et nos propres domaines.

Fallback: OpenPageRank (gratuit, pas de limite raisonnable).
"""

import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("diffusionbot.da_fetcher")


class DAFetcher:
    """Recupere le Domain Authority via Moz ou OpenPageRank."""

    MOZ_API = "https://lsapi.seomoz.com/v2/url_metrics"
    OPR_API = "https://openpagerank.com/api/v1.0/getPageRank"

    def __init__(
        self,
        moz_access_id: str = "",
        moz_secret_key: str = "",
        opr_api_key: str = "",
    ):
        self.moz_access_id = moz_access_id
        self.moz_secret_key = moz_secret_key
        self.opr_api_key = opr_api_key

    async def fetch_da(self, domain: str) -> dict | None:
        """
        Recupere le DA d'un domaine.
        Essaie Moz d'abord, puis OpenPageRank en fallback.
        Retourne: {"da": 45.2, "source": "moz"} ou None si echec.
        """
        # Normaliser le domaine
        domain = self._normalize_domain(domain)

        # Essayer Moz
        if self.moz_access_id and self.moz_secret_key:
            result = await self._fetch_moz(domain)
            if result:
                return result

        # Fallback OpenPageRank
        if self.opr_api_key:
            result = await self._fetch_openpagerank(domain)
            if result:
                return result

        logger.warning(f"DA fetch echoue pour {domain}: aucune API configuree ou disponible")
        return None

    async def fetch_da_batch(self, domains: list[str]) -> dict[str, dict | None]:
        """Recupere le DA pour plusieurs domaines."""
        results = {}
        for domain in domains:
            results[domain] = await self.fetch_da(domain)
        return results

    async def _fetch_moz(self, domain: str) -> dict | None:
        """Moz Links API v2."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.MOZ_API,
                    json={"targets": [domain]},
                    auth=(self.moz_access_id, self.moz_secret_key),
                )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("results"):
                    da = data["results"][0].get("domain_authority", 0)
                    logger.info(f"Moz DA pour {domain}: {da}")
                    return {"da": round(da, 1), "source": "moz"}

            if resp.status_code == 429:
                logger.warning("Moz API rate limit atteint")
            else:
                logger.warning(f"Moz API erreur {resp.status_code} pour {domain}")
            return None

        except Exception as e:
            logger.error(f"Moz API exception pour {domain}: {e}")
            return None

    async def _fetch_openpagerank(self, domain: str) -> dict | None:
        """OpenPageRank API (gratuit)."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    self.OPR_API,
                    params={"domains[]": domain},
                    headers={"API-OPR": self.opr_api_key},
                )

            if resp.status_code == 200:
                data = resp.json()
                if data.get("response") and data["response"][0].get("page_rank_decimal") is not None:
                    # OpenPageRank retourne un score 0-10, on le convertit en echelle ~0-100
                    opr_score = float(data["response"][0]["page_rank_decimal"])
                    da_estimate = opr_score * 10  # Approximation grossiere
                    logger.info(f"OpenPageRank pour {domain}: {opr_score} (DA estime: {da_estimate})")
                    return {"da": round(da_estimate, 1), "source": "openpagerank"}

            logger.warning(f"OpenPageRank erreur pour {domain}: {resp.status_code}")
            return None

        except Exception as e:
            logger.error(f"OpenPageRank exception pour {domain}: {e}")
            return None

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        """Extrait le domaine nu d'une URL."""
        if domain.startswith(("http://", "https://")):
            parsed = urlparse(domain)
            domain = parsed.netloc
        return domain.lower().strip().rstrip("/")
