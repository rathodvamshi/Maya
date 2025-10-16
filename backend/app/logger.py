import logging
from typing import Optional

# Create a logger for the app
logger = logging.getLogger("app_logger")
logger.setLevel(logging.INFO)

# Console handler with a simple format
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
logger.addHandler(console_handler)


def log_event(event: str, *, user_id: Optional[str] = None, task_id: Optional[str] = None, email: Optional[str] = None, **extra) -> None:
    parts = [f"event={event}"]
    if user_id:
        parts.append(f"user_id={user_id}")
    if task_id:
        parts.append(f"task_id={task_id}")
    if email:
        parts.append(f"email={email}")
    for k, v in (extra or {}).items():
        parts.append(f"{k}={v}")
    logger.info(" ".join(parts))
