from celery import Celery

from backend.app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "japonica",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "backend.app.tasks.notifications",
        "backend.app.modules.kanban.tasks",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "check-overdue-cards": {
            "task": "app.modules.kanban.tasks.check_overdue_cards",
            "schedule": 5 * 60,  # every 5 minutes
        },
        "process-outbox-events": {
            "task": "app.modules.kanban.tasks.process_outbox_events",
            "schedule": 10.0,
        },
    },
)
