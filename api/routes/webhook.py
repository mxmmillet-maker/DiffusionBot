import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import ContentWebhookPayload, WebhookResponse
from config.settings import Settings
from db.engine import get_db
from db.models import Contenu, Projet

router = APIRouter()
logger = logging.getLogger("diffusionbot.webhook")


def get_settings() -> Settings:
    return Settings()


@router.post("/content", response_model=WebhookResponse)
async def receive_content(
    payload: ContentWebhookPayload,
    x_webhook_secret: str = Header(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Endpoint appele par le CMS quand un nouveau contenu est publie."""
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    projet = db.execute(
        select(Projet).where(Projet.slug == payload.project_slug, Projet.actif.is_(True))
    ).scalar_one_or_none()

    if not projet:
        raise HTTPException(
            status_code=404, detail=f"Projet '{payload.project_slug}' introuvable ou inactif"
        )

    contenu_brut = payload.content_html or payload.content_markdown or ""

    contenu = Contenu(
        projet_id=projet.id,
        titre=payload.title,
        url_source=str(payload.url),
        contenu_brut=contenu_brut,
        mots_cles=payload.keywords,
        categorie=payload.category,
        statut="nouveau",
        received_at=datetime.now(timezone.utc),
    )
    db.add(contenu)
    db.commit()
    db.refresh(contenu)

    logger.info(f"Nouveau contenu recu: '{payload.title}' pour projet {payload.project_slug}")

    return WebhookResponse(
        status="ok",
        contenu_id=contenu.id,
        message=f"Contenu '{payload.title}' enregistre pour diffusion",
    )


@router.get("/status")
async def webhook_status():
    return {"status": "ok", "accepting": True}
