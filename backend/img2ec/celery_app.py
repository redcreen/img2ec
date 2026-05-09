from celery import Celery

from img2ec.config import get_settings

settings = get_settings()

celery_app = Celery(
    "img2ec",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["img2ec.tasks.pipeline_tasks"],
)

celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
