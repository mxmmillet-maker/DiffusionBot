from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import dashboard, health, webhook


def create_app() -> FastAPI:
    app = FastAPI(title="DiffusionBot", version="0.1.0", docs_url="/docs")

    app.include_router(health.router, tags=["health"])
    app.include_router(webhook.router, prefix="/webhook", tags=["webhook"])
    app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

    app.mount("/static", StaticFiles(directory="dashboard/static"), name="static")

    return app


app = create_app()
