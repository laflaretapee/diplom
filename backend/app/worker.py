from backend.app.celery_app import celery_app  # noqa: F401
from backend.app.db import models as _db_models  # noqa: F401
from backend.app.modules.kanban.tasks import (  # noqa: F401
    check_overdue_cards,
    process_outbox_events,
    send_card_assigned_notification,
    send_card_deadline_notification,
)
from backend.app.tasks.notifications import (  # noqa: F401
    send_franchisee_stage_notification,
    send_franchisee_task_status_notification,
    send_low_stock_notification,
    send_order_notification,
    send_overdue_franchisee_task_notifications,
    send_weekly_revenue_report,
)
from backend.app.tasks.scheduled import weekly_revenue_report  # noqa: F401

# Для обратной совместимости
app = celery_app


@celery_app.task(name="japonica.healthcheck")
def healthcheck() -> str:
    return "ok"
