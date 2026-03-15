from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field

from pixflix.pix_provider import build_pix_provider
from pixflix.services import Services, create_services
from pixflix.settings import Settings


class CreatePaymentRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    amount_cents: int | None = Field(default=None, gt=0)


class CreatePaymentResponse(BaseModel):
    payment_id: str
    provider_payment_id: str
    provider: str
    session_id: str
    amount_cents: int
    status: str
    pix_copy_paste_code: str
    qr_code_payload: str


class MusicRequestPayload(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    song_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=120)


class KioskStatusResponse(BaseModel):
    session_id: str
    credits: int
    queue_size: int


class QueueItemResponse(BaseModel):
    queue_id: str
    session_id: str
    song_id: str
    title: str
    created_at: str


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings.from_env()
    services = create_services(app_settings)
    pix_provider = build_pix_provider(app_settings.pix_provider)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            app.state.services.store.close()

    app = FastAPI(title="Pixflix API", version="0.1.0", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.services = services
    app.state.pix_provider = pix_provider

    def get_services() -> Services:
        return app.state.services

    def ensure_webhook_token(
        x_pixflix_webhook_token: str | None = Header(default=None),
    ) -> None:
        expected = app.state.settings.webhook_token
        if x_pixflix_webhook_token != expected:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid_webhook_token",
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/payments/create", response_model=CreatePaymentResponse)
    def create_payment(
        payload: CreatePaymentRequest,
        svc: Services = Depends(get_services),
    ) -> CreatePaymentResponse:
        amount_cents = payload.amount_cents or app.state.settings.default_amount_brl_cents
        payment = svc.payments.create_payment(session_id=payload.session_id, amount_cents=amount_cents)
        charge = app.state.pix_provider.create_charge(
            payment_id=payment.payment_id,
            amount_cents=payment.amount_cents,
        )
        return CreatePaymentResponse(
            payment_id=payment.payment_id,
            provider_payment_id=charge.provider_payment_id,
            provider=charge.provider,
            session_id=payment.session_id,
            amount_cents=payment.amount_cents,
            status=payment.status,
            pix_copy_paste_code=charge.pix_copy_paste_code,
            qr_code_payload=charge.qr_code_payload,
        )

    @app.post("/webhooks/pix")
    def pix_webhook(
        payload: dict[str, Any],
        _: None = Depends(ensure_webhook_token),
        svc: Services = Depends(get_services),
    ) -> dict[str, str]:
        try:
            event = app.state.pix_provider.parse_webhook(payload)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_webhook_payload")

        if event.status != "paid":
            return {"result": "ignored_non_paid_event"}
        try:
            payment = svc.webhook.process_paid_event(
                event_id=event.event_id,
                payment_id=event.payment_id,
            )
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment_not_found")
        return {"result": "processed", "payment_id": payment.payment_id, "status": payment.status}

    @app.post("/payments/{payment_id}/simulate-paid")
    def simulate_paid(
        payment_id: str,
        svc: Services = Depends(get_services),
    ) -> dict[str, str]:
        try:
            payment = svc.webhook.process_paid_event(
                event_id=f"sim_{payment_id}",
                payment_id=payment_id,
            )
        except KeyError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment_not_found")
        return {"result": "processed", "payment_id": payment.payment_id, "status": payment.status}

    @app.post("/music/request")
    def request_music(
        payload: MusicRequestPayload,
        svc: Services = Depends(get_services),
    ) -> dict[str, str]:
        try:
            remaining = svc.ledger.consume_credit(payload.session_id, units=1)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="insufficient_credit")

        queue_item = svc.player.enqueue(
            session_id=payload.session_id,
            song_id=payload.song_id,
            title=payload.title,
        )
        return {
            "result": "queued",
            "queue_id": queue_item.queue_id,
            "remaining_credits": str(remaining),
        }

    @app.get("/kiosk/{session_id}/status", response_model=KioskStatusResponse)
    def kiosk_status(session_id: str, svc: Services = Depends(get_services)) -> KioskStatusResponse:
        return KioskStatusResponse(
            session_id=session_id,
            credits=svc.ledger.balance(session_id),
            queue_size=len(svc.player.list_queue()),
        )

    @app.get("/player/queue", response_model=list[QueueItemResponse])
    def player_queue(svc: Services = Depends(get_services)) -> list[QueueItemResponse]:
        return [
            QueueItemResponse(
                queue_id=item.queue_id,
                session_id=item.session_id,
                song_id=item.song_id,
                title=item.title,
                created_at=item.created_at.isoformat(),
            )
            for item in svc.player.list_queue()
        ]

    return app


app = create_app()
