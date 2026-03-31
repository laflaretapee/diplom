from celery.schedules import crontab

from backend.app.celery_app import celery_app
from backend.app.tasks.notifications import send_weekly_revenue_report

celery_app.conf.beat_schedule = {
    "weekly-revenue-report": {
        "task": "notifications.send_weekly_revenue_report",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),  # Понедельник 8:00
    },
    "franchisee-overdue-scan": {
        "task": "notifications.send_overdue_franchisee_task_notifications",
        "schedule": crontab(minute="*/30"),
    },
}

@celery_app.task(name="tasks.weekly_revenue_report")
def weekly_revenue_report():
    """Compatibility wrapper for manual invocations of the old task name."""
    return send_weekly_revenue_report.run()
