"""
Google Analytics 4 Data API v1.
Recupere le traffic genere par les backlinks via UTM.
"""

import logging
from datetime import date, timedelta

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    FilterExpression,
    Filter,
    Metric,
    RunReportRequest,
)

logger = logging.getLogger("diffusionbot.ga4")


class GA4Client:
    """Client GA4 Data API pour tracker le traffic UTM des backlinks."""

    def __init__(self, credentials, property_id: str):
        self.property_id = property_id
        self.client = BetaAnalyticsDataClient(credentials=credentials)
        self._property = f"properties/{property_id}"

    def get_traffic_by_utm(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[dict]:
        """
        Traffic filtre par utm_medium=backlink, groupe par source + campaign.
        Retourne: [{"source": "medium", "campaign": "diffusionbot_karl-max",
                     "sessions": 42, "users": 38, "bounce_rate": 0.45, "avg_duration": 120.5}]
        """
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()

        request = RunReportRequest(
            property=self._property,
            dimensions=[
                Dimension(name="sessionSource"),
                Dimension(name="sessionCampaignName"),
                Dimension(name="sessionManualAdContent"),  # utm_content = post_id
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="totalUsers"),
                Metric(name="bounceRate"),
                Metric(name="averageSessionDuration"),
                Metric(name="conversions"),
            ],
            date_ranges=[
                DateRange(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
            ],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="sessionMedium",
                    string_filter=Filter.StringFilter(
                        value="backlink",
                        match_type=Filter.StringFilter.MatchType.EXACT,
                    ),
                )
            ),
        )

        try:
            response = self.client.run_report(request)
            results = []
            for row in response.rows:
                results.append({
                    "source": row.dimension_values[0].value,
                    "campaign": row.dimension_values[1].value,
                    "post_id": row.dimension_values[2].value or None,
                    "sessions": int(row.metric_values[0].value),
                    "users": int(row.metric_values[1].value),
                    "bounce_rate": float(row.metric_values[2].value),
                    "avg_duration": float(row.metric_values[3].value),
                    "conversions": int(row.metric_values[4].value),
                })
            logger.info(f"GA4: {len(results)} lignes UTM recuperees ({start_date} -> {end_date})")
            return results

        except Exception as e:
            logger.error(f"GA4 API error: {e}")
            return []

    def get_total_backlink_traffic(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> dict:
        """Aggrege total: sessions, users, bounce_rate pour utm_medium=backlink."""
        rows = self.get_traffic_by_utm(start_date, end_date)
        if not rows:
            return {"sessions": 0, "users": 0, "bounce_rate": 0, "conversions": 0}

        total_sessions = sum(r["sessions"] for r in rows)
        total_users = sum(r["users"] for r in rows)
        total_conversions = sum(r["conversions"] for r in rows)
        avg_bounce = (
            sum(r["bounce_rate"] * r["sessions"] for r in rows) / total_sessions
            if total_sessions > 0 else 0
        )
        return {
            "sessions": total_sessions,
            "users": total_users,
            "bounce_rate": round(avg_bounce, 3),
            "conversions": total_conversions,
        }
