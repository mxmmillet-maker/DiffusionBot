import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_dir: str = "logs", level: str = "INFO") -> logging.Logger:
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger("diffusionbot")
    root.setLevel(getattr(logging, level))

    # Rotating file handler (5 MB, 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "diffusionbot.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    return root
