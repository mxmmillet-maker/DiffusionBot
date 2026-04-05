"""
Google Search Console API.
Recupere positions, clics, impressions par page.
"""

import logging
from datetime import date, timedelta

from googleapiclient.discovery import build

logger = logging.getLogger("diffusionbot.gsc")


class GSCClient:
    """Client Google Search Console API."""

    def __init__(self, credentials, site_url: str):
        """
        site_url: URL du site dans GSC (ex: "https://karletmax.fr/" ou "sc-domain:karletmax.fr")
        """
        self.site_url = site_url
        self.service = build("searchconsole", "v1", credentials=credentials)

    def get_page_performance(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        page_filter: str | None = None,
    ) -> list[dict]:
        """
        Performance par page: clics, impressions, CTR, position.
        page_filter: filtre sur une URL specifique (optionnel).

        Retourne: [{"page": "https://...", "clicks": 42, "impressions": 1200,
                     "ctr": 0.035, "position": 12.5}]
        """
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()

        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["page"],
            "rowLimit": 1000,
        }

        if page_filter:
            body["dimensionFilterGroups"] = [{
                "filters": [{
                    "dimension": "page",
                    "operator": "contains",
                    "expression": page_filter,
                }]
            }]

        try:
            response = (
                self.service.searchanalytics()
                .query(siteUrl=self.site_url, body=body)
                .execute()
            )
            results = []
            for row in response.get("rows", []):
                results.append({
                    "page": row["keys"][0],
                    "clicks": row["clicks"],
                    "impressions": row["impressions"],
                    "ctr": round(row["ctr"], 4),
                    "position": round(row["position"], 1),
                })
            logger.info(f"GSC: {len(results)} pages recuperees ({start_date} -> {end_date})")
            return results

        except Exception as e:
            logger.error(f"GSC API error: {e}")
            return []

    def get_queries_for_page(
        self,
        page_url: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        """
        Keywords (queries) qui menent a une page specifique.
        Retourne: [{"query": "...", "clicks": 10, "impressions": 200, "position": 8.3}]
        """
        if not start_date:
            start_date = date.today() - timedelta(days=28)
        if not end_date:
            end_date = date.today()

        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "dimensionFilterGroups": [{
                "filters": [{
                    "dimension": "page",
                    "operator": "equals",
                    "expression": page_url,
                }]
            }],
            "rowLimit": 100,
        }

        try:
            response = (
                self.service.searchanalytics()
                .query(siteUrl=self.site_url, body=body)
                .execute()
            )
            results = []
            for row in response.get("rows", []):
                results.append({
                    "query": row["keys"][0],
                    "clicks": row["clicks"],
                    "impressions": row["impressions"],
                    "ctr": round(row["ctr"], 4),
                    "position": round(row["position"], 1),
                })
            return results

        except Exception as e:
            logger.error(f"GSC queries error: {e}")
            return []

    def get_aggregated_performance(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """Metriques aggregees du site: total clics, impressions, position moyenne."""
        pages = self.get_page_performance(start_date, end_date)
        if not pages:
            return {"clicks": 0, "impressions": 0, "avg_position": None, "pages_count": 0}

        total_clicks = sum(p["clicks"] for p in pages)
        total_impressions = sum(p["impressions"] for p in pages)
        # Position moyenne ponderee par impressions
        avg_pos = (
            sum(p["position"] * p["impressions"] for p in pages) / total_impressions
            if total_impressions > 0 else None
        )
        # Compter les keywords en top 10 et top 30
        top10 = sum(1 for p in pages if p["position"] <= 10)
        top30 = sum(1 for p in pages if p["position"] <= 30)

        return {
            "clicks": total_clicks,
            "impressions": total_impressions,
            "avg_position": round(avg_pos, 1) if avg_pos else None,
            "pages_count": len(pages),
            "keywords_top10": top10,
            "keywords_top30": top30,
        }
