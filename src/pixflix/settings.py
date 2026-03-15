from dataclasses import dataclass
import os
from typing import Literal


PixProviderName = Literal["mock", "efi_sandbox"]


@dataclass(frozen=True)
class Settings:
    webhook_token: str = "local-dev-token"
    default_amount_brl_cents: int = 100
    db_path: str = "pixflix.db"
    database_url: str = "sqlite:///pixflix.db"
    pix_provider: PixProviderName = "mock"

    def __post_init__(self) -> None:
        if self.database_url == "sqlite:///pixflix.db" and self.db_path != "pixflix.db":
            object.__setattr__(self, "database_url", f"sqlite:///{self.db_path}")

    @classmethod
    def from_env(cls) -> "Settings":
        raw_amount = os.getenv("PIXFLIX_DEFAULT_AMOUNT_CENTS", "100")
        db_path = os.getenv("PIXFLIX_DB_PATH", "pixflix.db")
        database_url = os.getenv("PIXFLIX_DATABASE_URL", f"sqlite:///{db_path}")
        pix_provider = os.getenv("PIXFLIX_PIX_PROVIDER", "mock")
        if pix_provider not in {"mock", "efi_sandbox"}:
            raise ValueError("PIXFLIX_PIX_PROVIDER must be 'mock' or 'efi_sandbox'")
        return cls(
            webhook_token=os.getenv("PIXFLIX_WEBHOOK_TOKEN", "local-dev-token"),
            default_amount_brl_cents=int(raw_amount),
            db_path=db_path,
            database_url=database_url,
            pix_provider=pix_provider,
        )
