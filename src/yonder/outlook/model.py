"""The ReserveOutlook contract — the JSON seam the dashboard renders from.

Carries the *inputs* the dashboard needs to both draw the chart and recompute
the fee-slider what-if client-side (start balance, history, projected
expenditures, planned fee changes, assumptions), plus presentation events.
All monetary values are CAD dollars. All fields nullable: real docs are
partial, and a missing depreciation report yields a `degraded` present-state
outlook rather than a fabricated projection.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field, field_validator


class BuildingMeta(BaseModel):
    name: str | None = None
    unit_label: str | None = None            # e.g. "#304"
    depreciation_report_date: datetime.date | None = None
    source_note: str | None = None           # e.g. "deprec. report 2022 · 4y old"


class Unit(BaseModel):
    entitlement_numerator: int | None = None
    entitlement_denominator: int | None = None
    strata_fee_monthly: float | None = None      # total monthly fee, dollars
    reserve_portion_monthly: float | None = None  # part of the fee going to the CRF


class BalancePoint(BaseModel):
    year: int
    balance: float                            # CRF balance, dollars


class Expenditure(BaseModel):
    """A projected major expenditure. Either a point (`year`) or a range
    (`start_year`/`end_year` with an expected `peak_year`)."""

    label: str
    amount: float                             # dollars
    year: int | None = None
    start_year: int | None = None
    end_year: int | None = None
    peak_year: int | None = None


class PlannedFeeChange(BaseModel):
    effective_year: int
    pct: float                                # fraction, e.g. 0.10 for +10%
    note: str | None = None

    @field_validator("pct")
    @classmethod
    def _pct_must_be_fraction(cls, v: float) -> float:
        # The mock's feeFactor does 1 + pct, so a percent-as-integer (10 instead
        # of 0.10) would silently 11x contributions. Reject at the schema layer.
        if not -1 < v < 1:
            raise ValueError(
                f"pct {v} looks like a percent, expected a fraction (-1 < pct < 1)"
            )
        return v


class TimelineEvent(BaseModel):
    """A dated marker in the bottom event lane. `year` may be fractional
    (2027.75 ≈ Oct). If `cluster_items` is set, this renders as a tap-to-expand
    count badge instead of a single labelled dot."""

    year: float
    row: int = 0                              # 0 = upper lane, 1 = lower lane
    type: str = "work"  # open vocabulary; typed core "work"|"fee"|"meeting"|"levy",
    # renderer falls back gracefully on unknown values (mirrors DocType's OTHER design)
    label: str | None = None
    cluster_items: list[str] | None = None


class Assumptions(BaseModel):
    interest_rate: float = 0.02               # annual, applied to the CRF balance
    base_annual_contribution: float | None = None  # dollars/year to CRF at fee_delta=0
    history_start_year: int | None = None
    projection_start_year: int | None = None  # "now"
    horizon_end_year: int | None = None
    sourced: bool = False                     # True = grounded in docs; False = placeholder


class ReserveOutlook(BaseModel):
    building: BuildingMeta = Field(default_factory=BuildingMeta)
    unit: Unit = Field(default_factory=Unit)
    assumptions: Assumptions = Field(default_factory=Assumptions)
    start_balance: float | None = None        # CRF balance at projection_start_year
    history: list[BalancePoint] = Field(default_factory=list)
    expenditures: list[Expenditure] = Field(default_factory=list)
    planned_fee_changes: list[PlannedFeeChange] = Field(default_factory=list)
    events: list[TimelineEvent] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None
