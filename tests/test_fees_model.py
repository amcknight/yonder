import json

from yonder.fees.model import (
    BuildingMeta,
    CategoryRow,
    FeeBreakdown,
    LineItem,
    RESERVE_CATEGORY,
    TotalFeePoint,
    UnitMeta,
)


def test_empty_breakdown_is_valid_and_not_degraded():
    """Absence is first-class: an all-empty breakdown must validate."""
    fb = FeeBreakdown()
    assert fb.categories == []
    assert fb.reserve is None
    assert fb.total_fee_series == []
    assert fb.degraded is False


def test_reserve_category_constant():
    assert RESERVE_CATEGORY == "Reserve contribution"


def test_category_row_carries_v11_prior_year_field_defaulting_none():
    row = CategoryRow(category="Utilities", building_annual=350000, personal_monthly=196)
    assert row.prior_year_annual is None       # v1.1 trend input; absent in v1
    assert row.line_items == []


def test_degraded_breakdown_carries_a_reason():
    fb = FeeBreakdown(degraded=True, degraded_reason="no operating budget line items found")
    assert fb.degraded is True
    assert "no operating budget" in fb.degraded_reason


def test_full_breakdown_round_trips_through_json():
    fb = FeeBreakdown(
        building=BuildingMeta(name="The Wexford", unit_label="#1802", fiscal_year=2024),
        unit=UnitMeta(lot_id="1802", operating_fee_monthly=521, reserve_fee_monthly=78,
                      total_fee_monthly=599),
        reserve=CategoryRow(category=RESERVE_CATEGORY, building_annual=139000, personal_monthly=78),
        categories=[
            CategoryRow(category="Utilities", building_annual=350000, personal_monthly=196,
                        line_items=[LineItem(label="Water & sewer", annual_amount=150000)]),
        ],
        total_fee_series=[TotalFeePoint(year=2024, monthly_fee=599)],
    )
    blob = fb.model_dump_json()
    assert FeeBreakdown.model_validate_json(blob) == fb
    assert FeeBreakdown.model_validate(json.loads(blob)) == fb
