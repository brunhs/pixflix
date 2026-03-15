from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from pixflix.models import Payment, QueueItem, new_id, now_utc
from pixflix.settings import Settings


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _from_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


class SqlStore:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, future=True)
        self._init_schema()

    def _init_schema(self) -> None:
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                paid_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS credits (
                session_id TEXT PRIMARY KEY,
                balance INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS queue_items (
                queue_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                song_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS processed_webhook_events (
                event_id TEXT PRIMARY KEY,
                payment_id TEXT NOT NULL,
                processed_at TEXT NOT NULL
            )
            """,
        ]
        with self.engine.begin() as conn:
            for ddl in ddl_statements:
                conn.execute(text(ddl))

    def close(self) -> None:
        self.engine.dispose()


class PaymentsService:
    def __init__(self, store: SqlStore) -> None:
        self.store = store

    def create_payment(self, session_id: str, amount_cents: int) -> Payment:
        payment = Payment(
            payment_id=new_id("pix"),
            session_id=session_id,
            amount_cents=amount_cents,
            status="pending",
            created_at=now_utc(),
            paid_at=None,
        )
        with self.store.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO payments (payment_id, session_id, amount_cents, status, created_at, paid_at)
                    VALUES (:payment_id, :session_id, :amount_cents, :status, :created_at, :paid_at)
                    """
                ),
                {
                    "payment_id": payment.payment_id,
                    "session_id": payment.session_id,
                    "amount_cents": payment.amount_cents,
                    "status": payment.status,
                    "created_at": _to_iso(payment.created_at),
                    "paid_at": _to_iso(payment.paid_at),
                },
            )
        return payment

    def get_payment(self, payment_id: str) -> Payment | None:
        with self.store.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT payment_id, session_id, amount_cents, status, created_at, paid_at
                    FROM payments WHERE payment_id = :payment_id
                    """
                ),
                {"payment_id": payment_id},
            ).fetchone()
        if row is None:
            return None
        data = row._mapping
        return Payment(
            payment_id=str(data["payment_id"]),
            session_id=str(data["session_id"]),
            amount_cents=int(data["amount_cents"]),
            status=str(data["status"]),
            created_at=_from_iso(str(data["created_at"])) or now_utc(),
            paid_at=_from_iso(data["paid_at"]) if data["paid_at"] else None,
        )

    def mark_paid(self, payment_id: str) -> Payment:
        payment = self.get_payment(payment_id)
        if payment is None:
            raise KeyError("payment_not_found")
        if payment.status != "paid":
            payment.status = "paid"
            payment.paid_at = now_utc()
            with self.store.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE payments
                        SET status = :status, paid_at = :paid_at
                        WHERE payment_id = :payment_id
                        """
                    ),
                    {
                        "status": payment.status,
                        "paid_at": _to_iso(payment.paid_at),
                        "payment_id": payment.payment_id,
                    },
                )
        return payment


class LedgerService:
    def __init__(self, store: SqlStore) -> None:
        self.store = store

    def balance(self, session_id: str) -> int:
        with self.store.engine.connect() as conn:
            row = conn.execute(
                text("SELECT balance FROM credits WHERE session_id = :session_id"),
                {"session_id": session_id},
            ).fetchone()
        if row is None:
            return 0
        return int(row._mapping["balance"])

    def add_credit(self, session_id: str, units: int = 1) -> int:
        with self.store.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO credits (session_id, balance)
                    VALUES (:session_id, :units)
                    ON CONFLICT(session_id) DO UPDATE SET balance = balance + excluded.balance
                    """
                ),
                {"session_id": session_id, "units": units},
            )
        return self.balance(session_id)

    def consume_credit(self, session_id: str, units: int = 1) -> int:
        with self.store.engine.begin() as conn:
            row = conn.execute(
                text("SELECT balance FROM credits WHERE session_id = :session_id"),
                {"session_id": session_id},
            ).fetchone()
            current = 0 if row is None else int(row._mapping["balance"])
            if current < units:
                raise ValueError("insufficient_credit")
            updated = current - units
            if row is None:
                conn.execute(
                    text("INSERT INTO credits (session_id, balance) VALUES (:session_id, :balance)"),
                    {"session_id": session_id, "balance": updated},
                )
            else:
                conn.execute(
                    text("UPDATE credits SET balance = :balance WHERE session_id = :session_id"),
                    {"balance": updated, "session_id": session_id},
                )
        return updated


class PlayerService:
    def __init__(self, store: SqlStore) -> None:
        self.store = store

    def enqueue(self, session_id: str, song_id: str, title: str) -> QueueItem:
        item = QueueItem(
            queue_id=new_id("queue"),
            session_id=session_id,
            song_id=song_id,
            title=title,
            created_at=now_utc(),
        )
        with self.store.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO queue_items (queue_id, session_id, song_id, title, created_at)
                    VALUES (:queue_id, :session_id, :song_id, :title, :created_at)
                    """
                ),
                {
                    "queue_id": item.queue_id,
                    "session_id": item.session_id,
                    "song_id": item.song_id,
                    "title": item.title,
                    "created_at": _to_iso(item.created_at),
                },
            )
        return item

    def list_queue(self) -> list[QueueItem]:
        with self.store.engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT queue_id, session_id, song_id, title, created_at
                    FROM queue_items
                    ORDER BY created_at ASC
                    """
                )
            ).fetchall()
        return [
            QueueItem(
                queue_id=str(row._mapping["queue_id"]),
                session_id=str(row._mapping["session_id"]),
                song_id=str(row._mapping["song_id"]),
                title=str(row._mapping["title"]),
                created_at=_from_iso(str(row._mapping["created_at"])) or now_utc(),
            )
            for row in rows
        ]


class PixWebhookService:
    def __init__(self, store: SqlStore, payments: PaymentsService, ledger: LedgerService) -> None:
        self.store = store
        self.payments = payments
        self.ledger = ledger

    def process_paid_event(self, event_id: str, payment_id: str) -> Payment:
        with self.store.engine.connect() as conn:
            row = conn.execute(
                text("SELECT event_id FROM processed_webhook_events WHERE event_id = :event_id"),
                {"event_id": event_id},
            ).fetchone()
        if row is not None:
            payment = self.payments.get_payment(payment_id)
            if payment is None:
                raise KeyError("payment_not_found")
            return payment

        payment = self.payments.get_payment(payment_id)
        if payment is None:
            raise KeyError("payment_not_found")

        first_time_paid = payment.status != "paid"
        if first_time_paid:
            payment = self.payments.mark_paid(payment_id)
            self.ledger.add_credit(session_id=payment.session_id, units=1)

        try:
            with self.store.engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO processed_webhook_events (event_id, payment_id, processed_at)
                        VALUES (:event_id, :payment_id, :processed_at)
                        """
                    ),
                    {
                        "event_id": event_id,
                        "payment_id": payment_id,
                        "processed_at": _to_iso(now_utc()),
                    },
                )
        except IntegrityError:
            # In case of race, event was already processed by another worker.
            pass
        return payment


@dataclass
class Services:
    store: SqlStore
    payments: PaymentsService
    ledger: LedgerService
    player: PlayerService
    webhook: PixWebhookService


def create_services(settings: Settings) -> Services:
    store = SqlStore(settings.database_url)
    payments = PaymentsService(store)
    ledger = LedgerService(store)
    player = PlayerService(store)
    webhook = PixWebhookService(store, payments, ledger)
    return Services(store=store, payments=payments, ledger=ledger, player=player, webhook=webhook)

