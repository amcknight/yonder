import pytest

from yonder.fees.compute import fee_breakdown
from yonder.fees.model import FeeBreakdown, RESERVE_CATEGORY
from yonder.fees.schema import BudgetLineItem, FeeExtract, LotFee


def _budget_extract() -> FeeExtract:
    return FeeExtract(
        building_name="The Spectrum",
        fiscal_year=2024,
        operating_budget=[
            BudgetLineItem(label="Water & sewer", parent_category="Utilities",
                           annual_amount=200000, fiscal_year=2024),
            BudgetLineItem(label="Heat", parent_category="Utilities",
                           annual_amount=150000, fiscal_year=2024),
            BudgetLineItem(label="Insurance premium", parent_category="Insurance",
                           annual_amount=182000, fiscal_year=2024),
            BudgetLineItem(label="Transfer to CRF", parent_category="Reserve contribution",
                           annual_amount=139000, fiscal_year=2024),
        ],
    )


def test_returns_a_feebreakdown():
    assert isinstance(fee_breakdown(_budget_extract()), FeeBreakdown)


def test_rolls_line_items_into_parent_categories():
    fb = fee_breakdown(_budget_extract())
    util = next(c for c in fb.categories if c.category == "Utilities")
    assert util.building_annual == 350000
    assert {li.label for li in util.line_items} == {"Water & sewer", "Heat"}


def test_categories_sorted_descending_by_building_annual():
    fb = fee_breakdown(_budget_extract())
    annuals = [c.building_annual for c in fb.categories]
    assert annuals == sorted(annuals, reverse=True)
    assert fb.categories[0].category == "Utilities"  # 350k beats Insurance 182k


def test_reserve_pinned_separately_not_in_spend_list():
    fb = fee_breakdown(_budget_extract())
    assert fb.reserve is not None
    assert fb.reserve.category == RESERVE_CATEGORY
    assert fb.reserve.building_annual == 139000
    assert all(c.category != RESERVE_CATEGORY for c in fb.categories)


def test_building_meta_carries_name_and_fiscal_year_and_source_note():
    fb = fee_breakdown(_budget_extract())
    assert fb.building.name == "The Spectrum"
    assert fb.building.fiscal_year == 2024
    assert "FY2024" in fb.building.source_note


def test_building_totals_only_when_no_fee_schedule():
    fb = fee_breakdown(_budget_extract())
    assert all(c.personal_monthly is None for c in fb.categories)
    assert fb.unit.operating_fee_monthly is None


def _extract_with_schedule() -> FeeExtract:
    e = _budget_extract()
    e.fee_schedule = [
        LotFee(lot_id="1802", entitlement=82, operating_monthly=521, crf_monthly=78),
        LotFee(lot_id="0101", entitlement=70, operating_monthly=445, crf_monthly=66),
    ]
    return e


def test_unit_meta_and_total_fee_populated_from_lot():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    assert fb.unit.lot_id == "1802"
    assert fb.unit.entitlement == 82
    assert fb.unit.operating_fee_monthly == 521
    assert fb.unit.reserve_fee_monthly == 78
    assert fb.unit.total_fee_monthly == 599
    assert fb.building.unit_label == "#1802"


def test_spend_personals_sum_to_the_operating_fee():
    # personal = share * operating_fee, and the shares sum to 1.
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    total = sum(c.personal_monthly for c in fb.categories)
    assert total == pytest.approx(521, abs=0.02)


def test_personal_share_proportional_to_building_annual():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    util = next(c for c in fb.categories if c.category == "Utilities")  # 350k
    spend_total = sum(c.building_annual for c in fb.categories)          # 350k + 182k = 532k
    assert util.personal_monthly == pytest.approx(350000 / spend_total * 521, abs=0.02)


def test_reserve_personal_uses_crf_not_a_share():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    assert fb.reserve.personal_monthly == 78  # the lot's CRF contribution, directly


def test_unknown_lot_falls_back_to_building_totals():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="9999")
    assert fb.unit.operating_fee_monthly is None
    assert all(c.personal_monthly is None for c in fb.categories)
    assert fb.reserve.personal_monthly is None


def test_no_lot_id_given_falls_back_to_building_totals():
    fb = fee_breakdown(_extract_with_schedule())  # lot_id omitted
    assert fb.unit.operating_fee_monthly is None
    assert all(c.personal_monthly is None for c in fb.categories)


def test_total_fee_series_has_one_current_year_point_when_lot_known():
    fb = fee_breakdown(_extract_with_schedule(), lot_id="1802")
    assert len(fb.total_fee_series) == 1
    assert fb.total_fee_series[0].year == 2024
    assert fb.total_fee_series[0].monthly_fee == 599


def test_no_total_series_without_a_known_lot():
    fb = fee_breakdown(_budget_extract())
    assert fb.total_fee_series == []


def test_single_year_budget_is_not_hard_degraded():
    # v1 norm: one budget year renders bars; the trend layer simply has no data.
    fb = fee_breakdown(_budget_extract())
    assert fb.degraded is False
    assert fb.categories  # bars present
    assert all(c.prior_year_annual is None for c in fb.categories)  # no trend inputs in v1


def test_degrades_when_no_operating_budget():
    fb = fee_breakdown(FeeExtract(building_name="Empty", fiscal_year=2024))
    assert fb.degraded is True
    assert "no operating budget" in fb.degraded_reason
    assert fb.categories == []
    assert fb.reserve is None
