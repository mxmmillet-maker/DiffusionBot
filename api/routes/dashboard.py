import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas import DashboardStats
from db.engine import get_db
from db.models import (
    AnalyticsSEO,
    AnalyticsTraffic,
    Plateforme,
    Post,
    ProjectDAHistory,
    Projet,
)

router = APIRouter()
logger = logging.getLogger("diffusionbot.dashboard")
templates = Jinja2Templates(directory="dashboard/templates")


def _render(request: Request, name: str, ctx: dict | None = None):
    return templates.TemplateResponse(request, name, context=ctx or {})


# ── HTML Pages ──


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request, db: Session = Depends(get_db)):
    stats = _build_stats(db)
    projets = db.execute(select(Projet).where(Projet.actif.is_(True))).scalars().all()
    recent_posts = (
        db.execute(select(Post).order_by(Post.created_at.desc()).limit(10)).scalars().all()
    )
    return _render(request, "overview.html", {
        "stats": stats, "projets": projets, "recent_posts": recent_posts,
    })


@router.get("/project/{slug}", response_class=HTMLResponse)
async def project_detail(request: Request, slug: str, db: Session = Depends(get_db)):
    projet = db.execute(select(Projet).where(Projet.slug == slug)).scalar_one_or_none()
    if not projet:
        return HTMLResponse("Projet introuvable", status_code=404)
    posts = (
        db.execute(
            select(Post).where(Post.projet_id == projet.id).order_by(Post.created_at.desc())
        )
        .scalars()
        .all()
    )
    return _render(request, "project.html", {"projet": projet, "posts": posts})


@router.get("/platforms", response_class=HTMLResponse)
async def platforms_list(request: Request, db: Session = Depends(get_db)):
    plateformes = (
        db.execute(select(Plateforme).order_by(Plateforme.score_composite.desc().nullslast()))
        .scalars()
        .all()
    )
    return _render(request, "platforms.html", {"plateformes": plateformes})


@router.get("/posts", response_class=HTMLResponse)
async def posts_list(request: Request, db: Session = Depends(get_db)):
    posts = db.execute(select(Post).order_by(Post.created_at.desc()).limit(100)).scalars().all()
    return _render(request, "posts.html", {"posts": posts})


@router.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request, db: Session = Depends(get_db)):
    return _render(request, "analytics.html")


# ── JSON API ──

@router.get("/api/stats", response_model=DashboardStats)
async def api_stats(db: Session = Depends(get_db)):
    return _build_stats(db)


# ── HTMX Partials ──

@router.get("/api/partials/kpis", response_class=HTMLResponse)
async def partials_kpis(request: Request, db: Session = Depends(get_db)):
    stats = _build_stats(db)
    return _render(request, "partials/_kpi_cards.html", {"stats": stats})


@router.get("/api/partials/analytics-kpis")
async def partials_analytics_kpis(db: Session = Depends(get_db)):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    sessions = (
        db.execute(
            select(func.sum(AnalyticsTraffic.sessions)).where(AnalyticsTraffic.date >= week_ago)
        ).scalar() or 0
    )
    users = (
        db.execute(
            select(func.sum(AnalyticsTraffic.users)).where(AnalyticsTraffic.date >= week_ago)
        ).scalar() or 0
    )
    clicks = (
        db.execute(
            select(func.sum(AnalyticsSEO.clicks)).where(AnalyticsSEO.date >= week_ago)
        ).scalar() or 0
    )
    avg_pos = (
        db.execute(
            select(func.avg(AnalyticsSEO.avg_position)).where(AnalyticsSEO.date >= week_ago)
        ).scalar()
    )
    return JSONResponse({
        "sessions": sessions, "users": users, "clicks": clicks,
        "avg_position": round(avg_pos, 1) if avg_pos else None,
    })


# ── Chart Data API ──

@router.get("/api/chart/backlinks")
async def chart_backlinks(db: Session = Depends(get_db)):
    labels, values = [], []
    for i in range(30, -1, -1):
        day = datetime.now(timezone.utc) - timedelta(days=i)
        day_end = day.replace(hour=23, minute=59, second=59)
        count = (
            db.execute(
                select(func.count(Post.id)).where(
                    Post.statut == "publie", Post.publie_at <= day_end
                )
            ).scalar() or 0
        )
        labels.append(day.strftime("%d/%m"))
        values.append(count)
    return JSONResponse({"labels": labels, "values": values})


@router.get("/api/chart/status")
async def chart_status(db: Session = Depends(get_db)):
    statuts = ["publie", "erreur", "planifie", "supprime", "404"]
    colors_map = {
        "publie": "#059669", "erreur": "#dc2626", "planifie": "#3b82f6",
        "supprime": "#6b7280", "404": "#d97706",
    }
    labels, values, colors = [], [], []
    for s in statuts:
        count = db.execute(select(func.count(Post.id)).where(Post.statut == s)).scalar() or 0
        if count > 0:
            labels.append(s.capitalize())
            values.append(count)
            colors.append(colors_map[s])
    return JSONResponse({"labels": labels, "values": values, "colors": colors})


@router.get("/api/chart/traffic-by-platform")
async def chart_traffic_by_platform(db: Session = Depends(get_db)):
    results = db.execute(
        select(Plateforme.nom, func.sum(AnalyticsTraffic.sessions).label("total"))
        .join(AnalyticsTraffic, AnalyticsTraffic.plateforme_id == Plateforme.id)
        .group_by(Plateforme.nom)
        .order_by(func.sum(AnalyticsTraffic.sessions).desc())
        .limit(10)
    ).all()
    return JSONResponse({"labels": [r[0] for r in results], "values": [r[1] for r in results]})


@router.get("/api/chart/positions")
async def chart_positions(db: Session = Depends(get_db)):
    labels, values = [], []
    for i in range(12, -1, -1):
        week_start = datetime.now(timezone.utc) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=7)
        avg = db.execute(
            select(func.avg(AnalyticsSEO.avg_position)).where(
                AnalyticsSEO.date >= week_start, AnalyticsSEO.date < week_end
            )
        ).scalar()
        labels.append(week_start.strftime("S%W"))
        values.append(round(avg, 1) if avg else None)
    return JSONResponse({"labels": labels, "values": values})


@router.get("/api/chart/project-da/{slug}")
async def chart_project_da(slug: str, db: Session = Depends(get_db)):
    projet = db.execute(select(Projet).where(Projet.slug == slug)).scalar_one_or_none()
    if not projet:
        return JSONResponse({"labels": [], "values": []})
    history = (
        db.execute(
            select(ProjectDAHistory)
            .where(ProjectDAHistory.projet_id == projet.id)
            .order_by(ProjectDAHistory.measured_at)
        ).scalars().all()
    )
    return JSONResponse({
        "labels": [h.measured_at.strftime("%m/%Y") for h in history],
        "values": [h.da_value for h in history],
    })


@router.get("/api/chart/project-traffic/{slug}")
async def chart_project_traffic(slug: str, db: Session = Depends(get_db)):
    projet = db.execute(select(Projet).where(Projet.slug == slug)).scalar_one_or_none()
    if not projet:
        return JSONResponse({"labels": [], "values": []})
    labels, values = [], []
    for i in range(12, -1, -1):
        week_start = datetime.now(timezone.utc) - timedelta(weeks=i)
        week_end = week_start + timedelta(days=7)
        sessions = (
            db.execute(
                select(func.sum(AnalyticsTraffic.sessions)).where(
                    AnalyticsTraffic.projet_id == projet.id,
                    AnalyticsTraffic.date >= week_start,
                    AnalyticsTraffic.date < week_end,
                )
            ).scalar() or 0
        )
        labels.append(week_start.strftime("S%W"))
        values.append(sessions)
    return JSONResponse({"labels": labels, "values": values})


@router.get("/api/chart/our-da")
async def chart_our_da(db: Session = Depends(get_db)):
    projets = db.execute(select(Projet).where(Projet.actif.is_(True))).scalars().all()
    all_history = (
        db.execute(select(ProjectDAHistory).order_by(ProjectDAHistory.measured_at))
        .scalars().all()
    )
    dates = sorted(set(h.measured_at.strftime("%m/%Y") for h in all_history))
    projects_data = []
    for p in projets:
        p_history = {
            h.measured_at.strftime("%m/%Y"): h.da_value
            for h in all_history if h.projet_id == p.id
        }
        projects_data.append({"name": p.nom, "values": [p_history.get(d) for d in dates]})
    return JSONResponse({"labels": dates, "projects": projects_data})


# ── Stats Helper ──

def _build_stats(db: Session) -> DashboardStats:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_posts = db.execute(select(func.count(Post.id))).scalar() or 0
    posts_today = db.execute(
        select(func.count(Post.id)).where(Post.publie_at >= today_start)
    ).scalar() or 0
    alive = db.execute(
        select(func.count(Post.id)).where(Post.statut == "publie")
    ).scalar() or 0
    dead = db.execute(
        select(func.count(Post.id)).where(Post.statut.in_(["supprime", "404"]))
    ).scalar() or 0
    dofollow = db.execute(
        select(func.count(Post.id)).where(Post.dofollow_confirme.is_(True))
    ).scalar() or 0
    nofollow = db.execute(
        select(func.count(Post.id)).where(Post.dofollow_confirme.is_(False))
    ).scalar() or 0
    platforms_active = db.execute(
        select(func.count(Plateforme.id)).where(Plateforme.actif.is_(True))
    ).scalar() or 0
    projects_active = db.execute(
        select(func.count(Projet.id)).where(Projet.actif.is_(True))
    ).scalar() or 0

    return DashboardStats(
        total_posts=total_posts, posts_today=posts_today,
        alive_links=alive, dead_links=dead,
        dofollow_count=dofollow, nofollow_count=nofollow,
        platforms_active=platforms_active, projects_active=projects_active,
    )
