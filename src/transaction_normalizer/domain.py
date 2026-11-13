"""Contratos del dominio; no depende de Qt."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


@dataclass(frozen=True)
class Issue:
    code: str
    field: str
    message: str


@dataclass(frozen=True)
class Transaction:
    id: str
    amount: Decimal
    currency: str
    timestamp: datetime
    status: Status
    source: str

    def to_dict(self) -> dict:
        return {**asdict(self), "timestamp": self.timestamp.isoformat().replace("+00:00", "Z"),
                "status": self.status.value}


@dataclass
class Record:
    index: int
    original: Any
    source: str | None = None
    normalized: Transaction | None = None
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def category(self) -> str:
        if self.normalized is not None:
            return "VALID"
        if any(error.code == "MISSING_FIELD" for error in self.errors):
            return "INCOMPLETE"
        return "INVALID"


@dataclass
class Metrics:
    processed: int = 0
    valid: int = 0
    invalid: int = 0  # Todas las rechazadas, incluidas las incompletas.
    incomplete: int = 0

    statuses: dict[str, int] = field(default_factory=lambda: {s.value: 0 for s in Status})
    currencies: dict[str, Decimal] = field(default_factory=dict)

    @property
    def invalid_only(self) -> int:
        return self.invalid - self.incomplete


@dataclass
class Batch:
    records: list[Record]
    metrics: Metrics
