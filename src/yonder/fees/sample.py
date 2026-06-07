"""A synthetic-but-realistic FeeBreakdown ("The Wexford") — the committed sample
that drives the mock and tests. Mirrors the locked mockup's numbers so the
data-driven render is verifiably identical. NOT real building data.

Single budget year (v1): no prior_year amounts, a one-point total_fee_series, so
the mock shows bars without the trend layer.
"""

from __future__ import annotations

from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    TotalFeePoint,
    UnitMeta,
)


def wexford_fee_sample() -> FeeBreakdown:
    return FeeBreakdown(
        building=BuildingMeta(
            name="The Wexford", unit_label="#1802", fiscal_year=2024,
            source_note="AGM budget FY2024 · synthetic",
        ),
        unit=UnitMeta(
            lot_id="1802", entitlement=82,
            operating_fee_monthly=521, reserve_fee_monthly=78, total_fee_monthly=599,
        ),
        reserve=CategoryRow(category=RESERVE_CATEGORY, building_annual=139000, personal_monthly=78),
        categories=[
            CategoryRow(category="Utilities", building_annual=350000, personal_monthly=196,
                        line_items=[
                            LineItem(label="Water & sewer", annual_amount=150000),
                            LineItem(label="Heat", annual_amount=90000),
                            LineItem(label="Electricity", annual_amount=60000),
                            LineItem(label="Gas", annual_amount=30000),
                            LineItem(label="Garbage", annual_amount=20000),
                        ]),
            CategoryRow(category="Repairs & maintenance", building_annual=211000, personal_monthly=118,
                        line_items=[
                            LineItem(label="General repairs", annual_amount=130000),
                            LineItem(label="Landscaping", annual_amount=81000),
                        ]),
            CategoryRow(category="Insurance", building_annual=182000, personal_monthly=102,
                        line_items=[LineItem(label="Insurance premium", annual_amount=182000)]),
            CategoryRow(category="Security & life-safety", building_annual=119000, personal_monthly=67,
                        line_items=[
                            LineItem(label="Concierge", annual_amount=80000),
                            LineItem(label="Fire monitoring", annual_amount=39000),
                        ]),
            CategoryRow(category="Building services", building_annual=43000, personal_monthly=24,
                        line_items=[LineItem(label="Elevator maintenance", annual_amount=43000)]),
            CategoryRow(category="Administration", building_annual=25000, personal_monthly=14,
                        line_items=[LineItem(label="Management fees", annual_amount=25000)]),
        ],
        total_fee_series=[TotalFeePoint(year=2024, monthly_fee=599)],
    )
