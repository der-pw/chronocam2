import logging
from datetime import datetime

# === Standard logger ===
logger = logging.getLogger("chronocam")
logger.setLevel(logging.WARNING)

# Console handler (keine Datei!)
console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# In-memory buffer (für Live-Ansicht)
LOG_BUFFER = []


def log(level: str, msg: str):
    """Write to both console and in-memory buffer."""
    entry = f"{datetime.now():%H:%M:%S} [{level.upper()}] {msg}"
    LOG_BUFFER.append(entry)
    if len(LOG_BUFFER) > 200:
        LOG_BUFFER.pop(0)

    level = level.lower()
    if level == "error":
        logger.error(msg)
    elif level in ("warn", "warning"):
        logger.warning(msg)
    else:
        logger.info(msg)


def get_recent_logs(n: int = 100):
    """Return the last n log entries from the in-memory buffer."""
    return LOG_BUFFER[-n:]
