from celery import Celery

from img2ec.config import get_settings

settings = get_settings()

celery_app = Celery(
    "img2ec",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "img2ec.tasks.pipeline_tasks",
        "img2ec.tasks.dim_tasks",
        "img2ec.tasks.scene_tasks",
    ],
)

celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1

if settings.celery_eager:
    # In-process synchronous mode: .delay() runs immediately in caller thread, no broker needed.
    celery_app.conf.task_always_eager = True
    # Don't propagate task exceptions out of .delay() — match production async semantics.
    # The task itself updates DB state (img.status=FAILED, err_msg=...) before raising,
    # so the frontend learns about failures via polling, not via a 500 on /process.
    celery_app.conf.task_eager_propagates = False


# Worker 启动时清掉孤儿 codex home 目录（SIGKILL / 崩溃残留）
from celery.signals import worker_ready, beat_init  # noqa: E402

@worker_ready.connect
def _cleanup_codex_orphans_on_boot(**_kwargs):
    try:
        from img2ec.infra.codex_image import cleanup_orphan_codex_homes
        n = cleanup_orphan_codex_homes(max_age_seconds=3600)
        if n:
            import logging
            logging.info(f"[img2ec] cleaned {n} orphan codex home dirs on worker boot")
    except Exception:
        pass
