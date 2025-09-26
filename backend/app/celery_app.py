# backend/app/celery_app.py

from celery import Celery
from app.config import settings

# This is the central Celery application instance.
# Both the worker and any web server process that needs to send tasks will import this.
celery_app = Celery(
    "maya_tasks",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    # Tell Celery where to find the task definitions.
    include=['app.celery_worker']
)

celery_app.conf.timezone = "UTC"