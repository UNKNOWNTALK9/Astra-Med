import logging
from logging.handlers import RotatingFileHandler
from config import BASE_DIR

_LOG_FILE = BASE_DIR / "astra_med.log"
_configured = False


def get_logger(name: str = "astra") -> logging.Logger:
    global _configured
    if not _configured:
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh = RotatingFileHandler(_LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
        _configured = True
    return logging.getLogger(name)
