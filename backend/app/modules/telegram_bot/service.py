from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.customer import Customer, CustomerSource

STEP_MARKER_PREFIX = "sales_bot_step:"


class RegistrationStep(StrEnum):
    NAME = "name"
    PHONE = "phone"
    ADDRESS = "address"
    ADDRESS_DETAILS = "address_details"


class CustomerLike(Protocol):
    name: str
    phone: str | None
    delivery_address: str | None
    notes: str | None


def _note_lines(notes: str | None) -> list[str]:
    return [line for line in (notes or "").splitlines() if line.strip()]


def get_registration_step(customer: CustomerLike) -> RegistrationStep | None:
    for line in _note_lines(customer.notes):
        if not line.startswith(STEP_MARKER_PREFIX):
            continue
        raw_step = line[len(STEP_MARKER_PREFIX) :].strip()
        try:
            return RegistrationStep(raw_step)
        except ValueError:
            return None
    return None


def set_registration_step(customer: CustomerLike, step: RegistrationStep | None) -> None:
    preserved = [
        line for line in _note_lines(customer.notes) if not line.startswith(STEP_MARKER_PREFIX)
    ]
    if step is not None:
        preserved.append(f"{STEP_MARKER_PREFIX}{step.value}")
    customer.notes = "\n".join(preserved) or None


def apply_registration_step(
    customer: CustomerLike,
    step: RegistrationStep,
    value: str,
) -> RegistrationStep | None:
    clean_value = value.strip()
    if step == RegistrationStep.NAME:
        customer.name = clean_value
        return RegistrationStep.PHONE
    if step == RegistrationStep.PHONE:
        customer.phone = clean_value
        return RegistrationStep.ADDRESS
    if step == RegistrationStep.ADDRESS:
        customer.delivery_address = clean_value
        return RegistrationStep.ADDRESS_DETAILS
    if clean_value and customer.delivery_address:
        customer.delivery_address = f"{customer.delivery_address}, {clean_value}"
    elif clean_value:
        customer.delivery_address = clean_value
    return None


async def get_or_create_sales_customer(
    db: AsyncSession,
    *,
    telegram_id: str,
    fallback_name: str,
) -> Customer:
    result = await db.execute(select(Customer).where(Customer.telegram_id == telegram_id))
    customer = result.scalar_one_or_none()
    if customer is not None:
        customer.source = CustomerSource.TELEGRAM
        return customer

    customer = Customer(
        name=fallback_name.strip() or "Клиент Telegram",
        telegram_id=telegram_id,
        source=CustomerSource.TELEGRAM,
    )
    db.add(customer)
    await db.flush()
    return customer
