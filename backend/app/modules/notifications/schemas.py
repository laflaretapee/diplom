from __future__ import annotations

from pydantic import BaseModel


class NotificationsModuleStatus(BaseModel):
    module: str
    status: str


class NotificationPreferences(BaseModel):
    order_created: bool = True
    order_cancelled: bool = True
    low_stock: bool = True
    franchisee_stage_changed: bool = True
    franchisee_task_changed: bool = True
    franchisee_task_overdue: bool = True
    weekly_revenue_report: bool = True


class NotificationPreferencesUpdate(BaseModel):
    order_created: bool | None = None
    order_cancelled: bool | None = None
    low_stock: bool | None = None
    franchisee_stage_changed: bool | None = None
    franchisee_task_changed: bool | None = None
    franchisee_task_overdue: bool | None = None
    weekly_revenue_report: bool | None = None


class TelegramLinkResponse(BaseModel):
    code: str
    expires_in: int
    instructions: str


class TelegramStatusResponse(BaseModel):
    linked: bool
    chat_id: str | None


class TelegramWebhookChat(BaseModel):
    id: int | str


class TelegramWebhookMessage(BaseModel):
    text: str | None = None
    chat: TelegramWebhookChat


class TelegramWebhookCallbackQuery(BaseModel):
    data: str | None = None
    message: TelegramWebhookMessage | None = None


class TelegramWebhookUpdate(BaseModel):
    message: TelegramWebhookMessage | None = None
    callback_query: TelegramWebhookCallbackQuery | None = None


class TelegramCommand(BaseModel):
    name: str
    args: list[str] = []


class OperationStatusResponse(BaseModel):
    ok: bool
