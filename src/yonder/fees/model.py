"""The FeeBreakdown contract — the JSON seam the Fee Breakdown mock renders from.

Carries everything the chart needs to draw client-side: building + unit meta, the
pinned Reserve row, the sorted spend-category rows (each with its building annual,
the user's personal monthly share, line items for tap-to-expand, and a nullable
prior-year amount the v1.1 trend layer will fill), and the total-fee series. All
monetary values are CAD dollars. All fields nullable: real docs are partial, a
missing fee schedule yields building-total-only rows (no personal sizing), and a
missing operating budget yields a `degraded` breakdown rather than empty bars.

This is reporting, not forecasting (unlike ReserveOutlook): no assumptions, no
projection. v1 emits a single budget year; the trend-layer fields (prior_year on
rows, multi-point total_fee_series) stay empty until v1.1 multi-year extraction.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

RESERVE_CATEGORY = "Reserve contribution"  # the one pinned, "saved not spent" category


class BuildingMeta(BaseModel):
    name: str | None = None
    unit_label: str | None = None       # e.g. "#1802"
    fiscal_year: int | None = None      # the budget year shown
    source_note: str | None = None      # e.g. "AGM budget FY2024"


class UnitMeta(BaseModel):
    lot_id: str | None = None
    entitlement: int | None = None
    operating_fee_monthly: float | None = None  # user's monthly operating contribution
    reserve_fee_monthly: float | None = None     # user's monthly CRF contribution
    total_fee_monthly: float | None = None       # operating + reserve


class LineItem(BaseModel):
    label: str
    annual_amount: float | None = None           # building annual dollars


class CategoryRow(BaseModel):
    category: str                                # parent category, e.g. "Utilities"
    building_annual: float | None = None         # sum of line items, building dollars
    personal_monthly: float | None = None        # user's monthly share, dollars (None = no fee schedule)
    prior_year_annual: float | None = None       # v1.1 trend input; None in v1
    line_items: list[LineItem] = Field(default_factory=list)


class TotalFeePoint(BaseModel):
    year: int
    monthly_fee: float                           # total monthly fee that year


class FeeBreakdown(BaseModel):
    building: BuildingMeta = Field(default_factory=BuildingMeta)
    unit: UnitMeta = Field(default_factory=UnitMeta)
    reserve: CategoryRow | None = None           # the pinned Reserve row (top), if known
    categories: list[CategoryRow] = Field(default_factory=list)  # spend, sorted desc by building_annual
    total_fee_series: list[TotalFeePoint] = Field(default_factory=list)  # v1: <=1 point
    degraded: bool = False
    degraded_reason: str | None = None
