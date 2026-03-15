from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4


PaymentStatus = Literal["pending", "paid", "expired"]


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class Payment:
    payment_id: str
    session_id: str
    amount_cents: int
    status: PaymentStatus
    created_at: datetime
    paid_at: datetime | None = None


@dataclass
class QueueItem:
    queue_id: str
    session_id: str
    song_id: str
    title: str
    created_at: datetime


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"

