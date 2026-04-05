"""Point d'entree CLI pour les workers via cron.

Usage:
    python -m cron.entrypoints diffusion
    python -m cron.entrypoints monitoring
    python -m cron.entrypoints intelligence
    python -m cron.entrypoints analytics
"""

import asyncio
import fcntl
import sys
from pathlib import Path

from config.logging import setup_logging
from config.settings import Settings


LOCK_DIR = Path("data")


def acquire_lock(worker_name: str):
    """Lock fichier pour empecher les executions concurrentes."""
    LOCK_DIR.mkdir(exist_ok=True)
    lock_path = LOCK_DIR / f".{worker_name}.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except BlockingIOError:
        print(f"Worker {worker_name} deja en cours d'execution, abandon.")
        sys.exit(0)


async def run_diffusion():
    settings = Settings()
    logger = setup_logging(level="DEBUG" if settings.debug else "INFO")
    lock = acquire_lock("diffusion")

    from db.engine import SessionLocal
    from services.content_reformulator import ContentReformulator
    from services.scheduler import HumanScheduler
    from services.scoring import PlatformScorer
    from services.telegram_notifier import TelegramNotifier
    from services.utm_builder import UTMBuilder
    from workers.diffusion import DiffusionWorker

    db = SessionLocal()
    try:
        worker = DiffusionWorker(
            db_session=db,
            reformulator=ContentReformulator(
                settings.anthropic_api_key, settings.anthropic_model
            ),
            scorer=PlatformScorer(),
            notifier=TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id),
            scheduler=HumanScheduler(),
            utm_builder=UTMBuilder(),
            max_retries=settings.max_retries,
        )
        await worker.run()
    finally:
        db.close()
        lock.close()


async def run_monitoring():
    settings = Settings()
    logger = setup_logging(level="DEBUG" if settings.debug else "INFO")
    lock = acquire_lock("monitoring")

    from db.engine import SessionLocal
    from services.link_checker import LinkChecker
    from services.telegram_notifier import TelegramNotifier
    from workers.monitoring import MonitoringWorker

    db = SessionLocal()
    try:
        worker = MonitoringWorker(
            db_session=db,
            link_checker=LinkChecker(timeout=settings.request_timeout),
            notifier=TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id),
        )
        await worker.run()
    finally:
        db.close()
        lock.close()


async def run_intelligence():
    settings = Settings()
    logger = setup_logging(level="DEBUG" if settings.debug else "INFO")
    lock = acquire_lock("intelligence")

    from db.engine import SessionLocal
    from services.da_fetcher import DAFetcher
    from services.scoring import PlatformScorer
    from services.telegram_notifier import TelegramNotifier
    from workers.intelligence import IntelligenceWorker

    db = SessionLocal()
    try:
        worker = IntelligenceWorker(
            db_session=db,
            da_fetcher=DAFetcher(
                moz_access_id=settings.moz_access_id,
                moz_secret_key=settings.moz_secret_key,
            ),
            scorer=PlatformScorer(),
            notifier=TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id),
        )
        await worker.run()
    finally:
        db.close()
        lock.close()


async def run_analytics():
    settings = Settings()
    logger = setup_logging(level="DEBUG" if settings.debug else "INFO")
    lock = acquire_lock("analytics")

    from db.engine import SessionLocal
    from services.da_fetcher import DAFetcher
    from services.telegram_notifier import TelegramNotifier
    from workers.analytics import AnalyticsWorker

    db = SessionLocal()
    try:
        worker = AnalyticsWorker(
            db_session=db,
            da_fetcher=DAFetcher(
                moz_access_id=settings.moz_access_id,
                moz_secret_key=settings.moz_secret_key,
            ),
            notifier=TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id),
            settings=settings,
        )
        await worker.run()
    finally:
        db.close()
        lock.close()


HANDLERS = {
    "diffusion": run_diffusion,
    "monitoring": run_monitoring,
    "intelligence": run_intelligence,
    "analytics": run_analytics,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in HANDLERS:
        print(f"Usage: python -m cron.entrypoints [{' | '.join(HANDLERS.keys())}]")
        sys.exit(1)

    command = sys.argv[1]
    print(f"Demarrage worker: {command}")
    asyncio.run(HANDLERS[command]())
