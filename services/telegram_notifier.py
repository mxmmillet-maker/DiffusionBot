import logging

import httpx

logger = logging.getLogger("diffusionbot.telegram")


class TelegramNotifier:
    """Envoi de rapports et alertes via Telegram Bot API."""

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = self.API_BASE.format(token=bot_token)
        self.enabled = bool(bot_token and chat_id)

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.enabled:
            logger.warning("Telegram non configure, message ignore")
            return False

        # Telegram limite a 4096 caracteres
        if len(text) > 4096:
            text = text[:4090] + "\n..."

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    },
                )
                if resp.status_code == 200:
                    return True
                logger.error(f"Telegram erreur: {resp.status_code} - {resp.text}")
                return False
            except Exception as e:
                logger.error(f"Telegram erreur envoi: {e}")
                return False

    async def send_daily_report(self, stats: dict):
        lines = [
            "<b>DiffusionBot — Rapport Quotidien</b>",
            "",
            f"Posts publies: <b>{stats.get('published', 0)}</b>",
            f"Echecs: <b>{stats.get('failed', 0)}</b>",
            f"Projets actifs: {stats.get('active_projects', 0)}",
            "",
        ]
        for ps in stats.get("per_project", []):
            lines.append(f"  {ps['name']}: {ps['count']} posts")

        if stats.get("errors"):
            lines.append("")
            lines.append("<b>Erreurs:</b>")
            for err in stats["errors"][:5]:
                lines.append(f"  - {err}")

        await self.send_message("\n".join(lines))

    async def send_alert(self, message: str):
        await self.send_message(f"<b>ALERTE</b>\n\n{message}")

    async def send_weekly_monitoring(self, stats: dict):
        lines = [
            "<b>DiffusionBot — Monitoring Hebdo</b>",
            "",
            f"Liens verifies: <b>{stats.get('verified', 0)}</b>",
            f"Liens morts: <b>{stats.get('dead', 0)}</b>",
            f"Changements dofollow: <b>{stats.get('dofollow_changes', 0)}</b>",
        ]
        if stats.get("problematic_platforms"):
            lines.append("")
            lines.append("<b>Plateformes problematiques:</b>")
            for p in stats["problematic_platforms"][:10]:
                lines.append(f"  - {p}")

        await self.send_message("\n".join(lines))

    async def send_weekly_analytics(self, stats: dict):
        lines = [
            "<b>DiffusionBot — Analytics Hebdo</b>",
            "",
            f"Sessions via backlinks: <b>{stats.get('total_sessions', 0)}</b>",
            f"Utilisateurs: <b>{stats.get('total_users', 0)}</b>",
        ]
        if stats.get("top_platforms"):
            lines.append("")
            lines.append("<b>Top plateformes (traffic):</b>")
            for p in stats["top_platforms"][:5]:
                lines.append(f"  - {p['name']}: {p['sessions']} sessions")

        if stats.get("position_changes"):
            lines.append("")
            lines.append("<b>Mouvements de position:</b>")
            for pc in stats["position_changes"][:5]:
                direction = "+" if pc["delta"] > 0 else ""
                lines.append(f"  - {pc['page']}: {direction}{pc['delta']} pos")

        await self.send_message("\n".join(lines))

    async def send_monthly_intelligence(self, stats: dict):
        lines = [
            "<b>DiffusionBot — Intelligence Mensuelle</b>",
            "",
            f"Plateformes analysees: <b>{stats.get('analyzed', 0)}</b>",
            f"Plateformes desactivees: <b>{stats.get('disabled', 0)}</b>",
        ]
        if stats.get("rising"):
            lines.append("")
            lines.append("<b>En hausse:</b>")
            for p in stats["rising"][:5]:
                lines.append(f"  - {p['name']}: DA {p['da']} (+{p['trend']:.1f})")

        if stats.get("declining"):
            lines.append("")
            lines.append("<b>En baisse:</b>")
            for p in stats["declining"][:5]:
                lines.append(f"  - {p['name']}: DA {p['da']} ({p['trend']:.1f})")

        await self.send_message("\n".join(lines))
