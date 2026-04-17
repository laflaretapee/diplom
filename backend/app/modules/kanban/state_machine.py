"""State machine for Kanban card statuses."""
from __future__ import annotations

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "new": ["in_progress"],
    "in_progress": ["in_review", "done"],
    "in_review": ["done", "in_progress"],
    "done": [],
}

STATUS_LABELS: dict[str, str] = {
    "new": "Новые",
    "in_progress": "В работе",
    "in_review": "На проверке",
    "done": "Выполнено",
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, [])


def get_allowed_transitions(status: str) -> list[str]:
    return ALLOWED_TRANSITIONS.get(status, [])
