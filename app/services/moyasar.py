import httpx
import base64
import logging
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

logger = logging.getLogger("moyasar")
settings = get_settings()

MOYASAR_API = "https://api.moyasar.com/v1"

_moyasar_secret_key: str = ""
_moyasar_publishable_key: str = ""


def configure(secret_key: str | None, publishable_key: str | None):
    global _moyasar_secret_key, _moyasar_publishable_key
    _moyasar_secret_key = secret_key or ""
    _moyasar_publishable_key = publishable_key or ""


def is_enabled() -> bool:
    return bool(_moyasar_secret_key)


def get_publishable_key() -> str:
    return _moyasar_publishable_key


def _auth_header() -> dict[str, str]:
    token = base64.b64encode(f"{_moyasar_secret_key}:".encode()).decode()
    return {"Authorization": f"Basic {token}"}


@dataclass
class MoyasarPaymentResult:
    id: str
    status: str
    amount: int
    currency: str
    url: str
    source_type: str


async def create_payment(
    amount_halala: int,
    description: str,
    callback_url: str,
    source_type: str = "creditcard",
    metadata: dict[str, str] | None = None,
) -> MoyasarPaymentResult:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MOYASAR_API}/payments",
            json={
                "amount": amount_halala,
                "currency": "SAR",
                "description": description,
                "source": {"type": source_type},
                "callback_url": callback_url,
                "metadata": metadata or {},
            },
            headers=_auth_header(),
            timeout=15,
        )
        if resp.status_code >= 400:
            logger.error(f"Moyasar payment creation failed: {resp.text}")
            raise ValueError(f"Moyasar error: {resp.json().get('message', 'unknown')}")

        data = resp.json()
        source_type = ""
        source_data = data.get("source", {})
        if isinstance(source_data, dict):
            source_type = source_data.get("type", "")

        return MoyasarPaymentResult(
            id=data["id"],
            status=data["status"],
            amount=data["amount"],
            currency=data.get("currency", "SAR"),
            url=data.get("url", ""),
            source_type=source_type,
        )


async def get_payment(payment_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{MOYASAR_API}/payments/{payment_id}",
            headers=_auth_header(),
            timeout=10,
        )
        if resp.status_code >= 400:
            raise ValueError(f"Payment not found: {payment_id}")
        return resp.json()


def verify_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    payment = payload.get("data", payload)
    if not payment.get("id"):
        raise ValueError("Invalid webhook payload")
    return payment
