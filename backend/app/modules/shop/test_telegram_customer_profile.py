from __future__ import annotations

from backend.app.db import models as _db_models  # noqa: F401
from backend.app.models.customer import Customer
from backend.app.modules.shop.schemas import TelegramCustomerProfile


def test_telegram_customer_profile_serializes_customer_fields() -> None:
    customer = Customer(
        name="Алина",
        phone="+79991234567",
        delivery_address="Пермь, Ленина 1",
        telegram_id="12345",
    )

    profile = TelegramCustomerProfile.model_validate(customer, from_attributes=True)

    assert profile.name == "Алина"
    assert profile.phone == "+79991234567"
    assert profile.delivery_address == "Пермь, Ленина 1"
    assert profile.telegram_id == "12345"
