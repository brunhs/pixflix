from fastapi.testclient import TestClient

from pixflix.app import create_app
from pixflix.settings import Settings


def test_payment_then_music_flow(tmp_path) -> None:
    db_path = tmp_path / "flow.db"
    settings = Settings(db_path=str(db_path), database_url=f"sqlite:///{db_path}")
    app = create_app(settings=settings)
    client = TestClient(app)

    create_payment = client.post(
        "/payments/create",
        json={"session_id": "terminal-1", "amount_cents": 100},
    )
    assert create_payment.status_code == 200
    assert create_payment.json()["provider"] == "mock"
    assert create_payment.json()["provider_payment_id"] == create_payment.json()["payment_id"]
    payment_id = create_payment.json()["payment_id"]

    blocked_music = client.post(
        "/music/request",
        json={"session_id": "terminal-1", "song_id": "song-7", "title": "Neon Track"},
    )
    assert blocked_music.status_code == 409
    assert blocked_music.json()["detail"] == "insufficient_credit"

    paid = client.post(f"/payments/{payment_id}/simulate-paid")
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"

    accepted_music = client.post(
        "/music/request",
        json={"session_id": "terminal-1", "song_id": "song-7", "title": "Neon Track"},
    )
    assert accepted_music.status_code == 200
    assert accepted_music.json()["result"] == "queued"
    assert accepted_music.json()["remaining_credits"] == "0"

    queue = client.get("/player/queue")
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    assert queue.json()[0]["song_id"] == "song-7"


def test_webhook_token_and_idempotency(tmp_path) -> None:
    db_path = tmp_path / "webhook.db"
    settings = Settings(db_path=str(db_path), database_url=f"sqlite:///{db_path}")
    app = create_app(settings=settings)
    client = TestClient(app)

    create_payment = client.post(
        "/payments/create",
        json={"session_id": "terminal-2", "amount_cents": 100},
    )
    payment_id = create_payment.json()["payment_id"]

    unauthorized = client.post(
        "/webhooks/pix",
        json={"event_id": "evt-1", "payment_id": payment_id, "status": "paid"},
    )
    assert unauthorized.status_code == 401

    headers = {"x-pixflix-webhook-token": "local-dev-token"}
    first = client.post(
        "/webhooks/pix",
        json={"event_id": "evt-1", "payment_id": payment_id, "status": "paid"},
        headers=headers,
    )
    assert first.status_code == 200

    second = client.post(
        "/webhooks/pix",
        json={"event_id": "evt-1", "payment_id": payment_id, "status": "paid"},
        headers=headers,
    )
    assert second.status_code == 200

    status = client.get("/kiosk/terminal-2/status")
    assert status.status_code == 200
    assert status.json()["credits"] == 1


def test_data_persists_between_app_restarts(tmp_path) -> None:
    db_path = str(tmp_path / "persist.db")
    settings = Settings(db_path=db_path, database_url=f"sqlite:///{db_path}")

    app1 = create_app(settings=settings)
    client1 = TestClient(app1)

    create_payment = client1.post(
        "/payments/create",
        json={"session_id": "terminal-3", "amount_cents": 100},
    )
    payment_id = create_payment.json()["payment_id"]
    client1.post(f"/payments/{payment_id}/simulate-paid")
    client1.post(
        "/music/request",
        json={"session_id": "terminal-3", "song_id": "song-9", "title": "Arcade Rush"},
    )
    app1.state.services.store.close()

    app2 = create_app(settings=settings)
    client2 = TestClient(app2)

    queue = client2.get("/player/queue")
    assert queue.status_code == 200
    assert len(queue.json()) == 1
    assert queue.json()[0]["title"] == "Arcade Rush"


def test_efi_sandbox_webhook_payload_support(tmp_path) -> None:
    db_path = tmp_path / "efi.db"
    settings = Settings(
        db_path=str(db_path),
        database_url=f"sqlite:///{db_path}",
        pix_provider="efi_sandbox",
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    create_payment = client.post(
        "/payments/create",
        json={"session_id": "terminal-efi", "amount_cents": 100},
    )
    assert create_payment.status_code == 200
    payment_id = create_payment.json()["payment_id"]
    assert create_payment.json()["provider"] == "efi_sandbox"

    headers = {"x-pixflix-webhook-token": "local-dev-token"}
    webhook = client.post(
        "/webhooks/pix",
        json={"id": "evt-efi-1", "pix": [{"txid": payment_id}]},
        headers=headers,
    )
    assert webhook.status_code == 200

    status = client.get("/kiosk/terminal-efi/status")
    assert status.status_code == 200
    assert status.json()["credits"] == 1
