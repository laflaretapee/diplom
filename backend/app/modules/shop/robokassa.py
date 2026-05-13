from __future__ import annotations

import hashlib
from urllib.parse import urlencode

from backend.app.core.config import get_settings

ROBOKASSA_URL = "https://auth.robokassa.ru/Merchant/Index.aspx"


def _md5(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def build_payment_url(*, out_sum: str, invoice_id: str, description: str) -> str:
    settings = get_settings()
    signature = _md5(
        f"{settings.robokassa_merchant_login}:{out_sum}:{invoice_id}:{settings.robokassa_password1}"
    )
    params = {
        "MerchantLogin": settings.robokassa_merchant_login,
        "OutSum": out_sum,
        "InvId": invoice_id,
        "Description": description,
        "SignatureValue": signature,
        "IsTest": "1" if settings.robokassa_is_test else "0",
        "Culture": "ru",
    }
    return f"{ROBOKASSA_URL}?{urlencode(params)}"


def validate_result_signature(*, out_sum: str, invoice_id: str, signature: str) -> bool:
    settings = get_settings()
    expected = _md5(f"{out_sum}:{invoice_id}:{settings.robokassa_password2}")
    return expected.lower() == signature.lower()
