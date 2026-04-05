from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base
    environment: str = "production"
    debug: bool = False
    base_dir: Path = Path(__file__).resolve().parent.parent

    # Database
    database_url: str = "sqlite:///data/diffusionbot.db"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8420
    webhook_secret: str = ""

    # Claude API
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Moz API
    moz_access_id: str = ""
    moz_secret_key: str = ""

    # Google OAuth
    google_service_account_file: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""

    # Encryption
    fernet_key: str = ""

    # Limits
    max_posts_per_day_global: int = 10
    max_retries: int = 3
    request_timeout: int = 30

    model_config = {"env_file": ".env", "env_prefix": "DIFFBOT_"}
