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
