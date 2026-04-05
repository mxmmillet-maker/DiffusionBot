from urllib.parse import urlencode, urlparse, urlunparse, parse_qs


class UTMBuilder:
    """Genere des URLs avec parametres UTM pour tracer les backlinks dans GA4."""

    PREFIX = "diffusionbot"

    def build(
        self,
        target_url: str,
        plateforme_slug: str,
        projet_slug: str,
        post_id: int,
    ) -> str:
        """Ajoute les UTM au backlink cible.

        Resultat: https://example.com/page?utm_source=medium&utm_medium=backlink
                  &utm_campaign=diffusionbot_karl-max&utm_content=42
        """
        utm_params = {
            "utm_source": plateforme_slug,
            "utm_medium": "backlink",
            "utm_campaign": f"{self.PREFIX}_{projet_slug}",
            "utm_content": str(post_id),
        }
        return self._append_params(target_url, utm_params)

    def get_utm_dict(
        self,
        plateforme_slug: str,
        projet_slug: str,
        post_id: int,
    ) -> dict:
        """Retourne les UTM sous forme de dict (pour stockage en DB)."""
        return {
            "utm_source": plateforme_slug,
            "utm_medium": "backlink",
            "utm_campaign": f"{self.PREFIX}_{projet_slug}",
            "utm_content": str(post_id),
        }

    @staticmethod
    def _append_params(url: str, params: dict) -> str:
        parsed = urlparse(url)
        existing = parse_qs(parsed.query)
        existing.update({k: [v] for k, v in params.items()})
        flat = {k: v[0] for k, v in existing.items()}
        new_query = urlencode(flat)
        return urlunparse(parsed._replace(query=new_query))
