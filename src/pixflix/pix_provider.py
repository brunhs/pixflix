from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from pixflix.settings import PixProviderName


@dataclass(frozen=True)
class PixCharge:
    provider: PixProviderName
    provider_payment_id: str
    pix_copy_paste_code: str
    qr_code_payload: str


@dataclass(frozen=True)
class PixWebhookEvent:
    event_id: str
    payment_id: str
    status: str


class PixProvider(Protocol):
    provider_name: PixProviderName

    def create_charge(self, payment_id: str, amount_cents: int) -> PixCharge:
        ...

    def parse_webhook(self, payload: dict[str, Any]) -> PixWebhookEvent:
        ...


class MockPixProvider:
    provider_name: PixProviderName = "mock"

    def create_charge(self, payment_id: str, amount_cents: int) -> PixCharge:
        amount_str = f"{Decimal(amount_cents) / Decimal(100):.2f}"
        return PixCharge(
            provider=self.provider_name,
            provider_payment_id=payment_id,
            pix_copy_paste_code=f"000201PIXFLIX{payment_id}AMOUNT{amount_str}",
            qr_code_payload=f"pixflix://pay/{payment_id}",
        )

    def parse_webhook(self, payload: dict[str, Any]) -> PixWebhookEvent:
        # Generic internal payload format.
        if {"event_id", "payment_id", "status"} <= payload.keys():
            return PixWebhookEvent(
                event_id=str(payload["event_id"]),
                payment_id=str(payload["payment_id"]),
                status=str(payload["status"]),
            )
        raise ValueError("unsupported_webhook_payload")


class EfiSandboxPixProvider:
    provider_name: PixProviderName = "efi_sandbox"

    def create_charge(self, payment_id: str, amount_cents: int) -> PixCharge:
        # Placeholder sandbox contract; replace with real HTTP API call once credentials are configured.
        amount_str = f"{Decimal(amount_cents) / Decimal(100):.2f}"
        return PixCharge(
            provider=self.provider_name,
            provider_payment_id=payment_id,
            pix_copy_paste_code=f"000201EFI{payment_id}AMOUNT{amount_str}",
            qr_code_payload=f"efi-sandbox://pix/{payment_id}",
        )

    def parse_webhook(self, payload: dict[str, Any]) -> PixWebhookEvent:
        # Efí-like webhook format:
        # {
        #   "id": "evt_123",
        #   "pix": [{"txid": "pix_abc", ...}]
        # }
        if "id" in payload and isinstance(payload.get("pix"), list) and payload["pix"]:
            first_pix = payload["pix"][0]
            if isinstance(first_pix, dict) and "txid" in first_pix:
                return PixWebhookEvent(
                    event_id=str(payload["id"]),
                    payment_id=str(first_pix["txid"]),
                    status="paid",
                )
        # Fallback to generic format for compatibility in tests/tools.
        return MockPixProvider().parse_webhook(payload)


def build_pix_provider(provider_name: PixProviderName) -> PixProvider:
    if provider_name == "mock":
        return MockPixProvider()
    if provider_name == "efi_sandbox":
        return EfiSandboxPixProvider()
    raise ValueError(f"unsupported_pix_provider:{provider_name}")

