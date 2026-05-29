"""The StrataExtract contract — what a strata PDF becomes.

v0 seed, not frozen. All fields nullable (real docs are partial; absence is a
first-class state — never invent). Provenance + confidence attach at FACT
granularity: each list item and each top-level group, not every scalar.
Doc type is an open vocabulary: a typed core plus OTHER + free label, so an
unrecognized doc degrades gracefully instead of being force-fit.
"""

from __future__ import annotations

import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocType(str, Enum):
    AGM_MINUTES = "agm_minutes"
    SGM_MINUTES = "sgm_minutes"
    DEPRECIATION_REPORT = "depreciation_report"
    FINANCIAL_STATEMENT = "financial_statement"
    FORM_B = "form_b"
    BYLAWS = "bylaws"
    OTHER = "other"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReserveTrend(str, Enum):
    RISING = "rising"
    FLAT = "flat"
    DECLINING = "declining"
    UNKNOWN = "unknown"


class Provenance(BaseModel):
    page: int | None = None
    doc_id: str | None = Field(
        default=None, description="Sub-document id within a combined PDF, if any."
    )
    confidence: Confidence = Confidence.MEDIUM


class Building(BaseModel):
    name: str | None = None
    address: str | None = None
    provenance: Provenance | None = None


class UnitEntitlement(BaseModel):
    numerator: int | None = None
    denominator: int | None = None
    provenance: Provenance | None = None

    @classmethod
    def from_ratio(cls, ratio: str) -> "UnitEntitlement":
        parts = ratio.split("/")
        if len(parts) != 2:
            raise ValueError(f"Not a ratio: {ratio!r}")
        num, den = (p.strip() for p in parts)
        if not (num.isdigit() and den.isdigit()):
            raise ValueError(f"Not a ratio: {ratio!r}")
        return cls(numerator=int(num), denominator=int(den))


class FoundDocument(BaseModel):
    type: DocType = DocType.OTHER
    type_label: str | None = Field(
        default=None, description="Free-text label when type is OTHER."
    )
    issue_date: datetime.date | None = None
    period_covered: str | None = None
    provenance: Provenance | None = None


class Meeting(BaseModel):
    type: str | None = Field(default=None, description='"AGM" or "SGM".')
    date: datetime.date | None = None
    provenance: Provenance | None = None


class SpecialLevy(BaseModel):
    amount: float | None = None
    date_approved: datetime.date | None = None
    purpose: str | None = None
    provenance: Provenance | None = None


class Litigation(BaseModel):
    present: bool | None = None
    summary: str | None = None
    provenance: Provenance | None = None


class ReserveFund(BaseModel):
    balance: float | None = None
    as_of_date: datetime.date | None = None
    trend: ReserveTrend = ReserveTrend.UNKNOWN
    provenance: Provenance | None = None


class StrataExtract(BaseModel):
    building: Building = Field(default_factory=Building)
    unit_entitlement: UnitEntitlement | None = None
    documents: list[FoundDocument] = Field(default_factory=list)
    meetings: list[Meeting] = Field(default_factory=list)
    special_levies: list[SpecialLevy] = Field(default_factory=list)
    litigation: Litigation | None = None
    reserve_fund: ReserveFund | None = None
