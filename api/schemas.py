from datetime import datetime

from pydantic import BaseModel, HttpUrl


class ContentWebhookPayload(BaseModel):
    project_slug: str
    title: str
    url: HttpUrl
    content_html: str | None = None
    content_markdown: str | None = None
    keywords: list[str] = []
    category: str | None = None


class WebhookResponse(BaseModel):
    status: str
    contenu_id: int
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime


class DashboardStats(BaseModel):
    total_posts: int
    posts_today: int
    alive_links: int
    dead_links: int
    dofollow_count: int
    nofollow_count: int
    platforms_active: int
    projects_active: int
