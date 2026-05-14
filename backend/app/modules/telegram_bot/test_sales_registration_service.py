from __future__ import annotations

from backend.app.modules.telegram_bot.service import (
    RegistrationStep,
    apply_registration_step,
    get_registration_step,
    set_registration_step,
)


class DummyCustomer:
    def __init__(self, notes: str | None = None) -> None:
        self.name = "Клиент"
        self.phone = None
        self.delivery_address = None
        self.notes = notes


def test_registration_step_marker_preserves_existing_notes() -> None:
    customer = DummyCustomer("Любит острое")

    set_registration_step(customer, RegistrationStep.PHONE)

    assert customer.notes == "Любит острое\nsales_bot_step:phone"
    assert get_registration_step(customer) == RegistrationStep.PHONE


def test_registration_step_marker_replaces_previous_marker() -> None:
    customer = DummyCustomer("sales_bot_step:name\nКомментарий")

    set_registration_step(customer, RegistrationStep.ADDRESS_DETAILS)

    assert customer.notes == "Комментарий\nsales_bot_step:address_details"
    assert get_registration_step(customer) == RegistrationStep.ADDRESS_DETAILS


def test_registration_step_marker_can_be_removed() -> None:
    customer = DummyCustomer("Комментарий\nsales_bot_step:address_details")

    set_registration_step(customer, None)

    assert customer.notes == "Комментарий"
    assert get_registration_step(customer) is None


def test_apply_registration_step_updates_customer_fields_and_next_step() -> None:
    customer = DummyCustomer()

    next_step = apply_registration_step(customer, RegistrationStep.NAME, "Алина")
    assert customer.name == "Алина"
    assert next_step == RegistrationStep.PHONE

    next_step = apply_registration_step(customer, RegistrationStep.PHONE, "+79991234567")
    assert customer.phone == "+79991234567"
    assert next_step == RegistrationStep.ADDRESS

    next_step = apply_registration_step(customer, RegistrationStep.ADDRESS, "Пермь, Ленина 1")
    assert customer.delivery_address == "Пермь, Ленина 1"
    assert next_step == RegistrationStep.ADDRESS_DETAILS

    next_step = apply_registration_step(customer, RegistrationStep.ADDRESS_DETAILS, "кв. 12")
    assert customer.delivery_address == "Пермь, Ленина 1, кв. 12"
    assert next_step is None


def test_apply_address_details_does_not_duplicate_empty_details() -> None:
    customer = DummyCustomer()
    customer.delivery_address = "Пермь, Ленина 1"

    next_step = apply_registration_step(customer, RegistrationStep.ADDRESS_DETAILS, "  ")

    assert customer.delivery_address == "Пермь, Ленина 1"
    assert next_step is None
