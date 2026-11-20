"""Corporate history records. Dollars stay whole numbers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CorporateEvent:
    id: str
    day: int
    year: int
    kind: str
    title: str
    detail: str = ""
    importance: int = 1
    entities: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordEntry:
    id: str
    title: str
    value: float
    day: int
    detail: str = ""


@dataclass(frozen=True)
class CorporateEra:
    id: str
    title: str
    start_day: int
    end_day: int | None
    reason: str


@dataclass(frozen=True)
class AnnualReport:
    year: int
    start_day: int
    end_day: int
    financials: dict[str, Any]
    operations: dict[str, Any]
    highlights: tuple[CorporateEvent, ...]
    records: tuple[RecordEntry, ...]
    eras: tuple[CorporateEra, ...]
    lessons: tuple[str, ...]
