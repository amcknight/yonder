"""A synthetic-but-realistic ReserveOutlook ("The Wexford") — the committed
sample that drives the mock and tests. Mirrors the locked mockup's data so the
data-driven render is verifiably identical. NOT real building data."""

from __future__ import annotations

from yonder.outlook.model import (
    Assumptions,
    BalancePoint,
    BuildingMeta,
    Expenditure,
    PlannedFeeChange,
    ReserveOutlook,
    TimelineEvent,
    Unit,
)

_HISTORY = [
    (2020, 260000), (2021, 300000), (2022, 215000), (2023, 285000),
    (2024, 360000), (2025, 415000), (2026, 420000),
]


def wexford_sample() -> ReserveOutlook:
    return ReserveOutlook(
        building=BuildingMeta(
            name="The Wexford", unit_label="#304",
            source_note="deprec. report 2022 · 4y old",
        ),
        unit=Unit(
            entitlement_numerator=18, entitlement_denominator=2719,
            strata_fee_monthly=486, reserve_portion_monthly=50,
        ),
        assumptions=Assumptions(
            interest_rate=0.02, base_annual_contribution=90000,
            history_start_year=2020, projection_start_year=2026,
            horizon_end_year=2041, sourced=False,
        ),
        start_balance=420000,
        history=[BalancePoint(year=y, balance=b) for y, b in _HISTORY],
        expenditures=[
            Expenditure(label="Roof", amount=180000, year=2028),
            Expenditure(label="Plumb", amount=150000, year=2030),
            Expenditure(label="Elev", amount=240000, year=2035),
            Expenditure(label="HVAC", amount=200000, year=2038),
            Expenditure(label="Envelope", amount=1100000,
                        start_year=2031, end_year=2033, peak_year=2032),
        ],
        planned_fee_changes=[
            PlannedFeeChange(effective_year=2028, pct=0.10),
            PlannedFeeChange(effective_year=2031, pct=0.06),
        ],
        events=[
            TimelineEvent(year=2028, row=0, type="work", label="Roof 180k"),
            TimelineEvent(year=2032, row=0, type="work", label="Envelope 1.1M"),
            TimelineEvent(year=2035, row=0, type="work", label="Elev 240k"),
            TimelineEvent(year=2027.75, row=1, type="fee", label="+10% plan"),
            TimelineEvent(year=2038, row=1, type="work", label="HVAC 200k"),
            TimelineEvent(year=2030, row=1, type="meeting",
                          cluster_items=["Plumbing 150k", "+6% planned", "AGM 2030"]),
        ],
    )
