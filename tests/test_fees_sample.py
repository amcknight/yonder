import json

from yonder.fees.model import FeeBreakdown, RESERVE_CATEGORY
from yonder.fees.sample import wexford_fee_sample


def test_sample_validates_and_has_expected_shape():
    fb = wexford_fee_sample()
    assert isinstance(fb, FeeBreakdown)
    assert fb.degraded is False
    assert fb.reserve is not None and fb.reserve.category == RESERVE_CATEGORY
    assert fb.unit.lot_id == "1802"
    assert len(fb.categories) == 6
    assert fb.categories[0].category == "Utilities"  # largest


def test_sample_categories_are_sorted_descending():
    annuals = [c.building_annual for c in wexford_fee_sample().categories]
    assert annuals == sorted(annuals, reverse=True)


def test_sample_spend_personals_sum_to_operating_fee():
    fb = wexford_fee_sample()
    total = sum(c.personal_monthly for c in fb.categories)
    assert abs(total - fb.unit.operating_fee_monthly) <= 1  # within rounding


def test_sample_has_a_multi_line_expandable_category():
    fb = wexford_fee_sample()
    assert any(len(c.line_items) > 1 for c in fb.categories)


def test_sample_round_trips_through_plain_json():
    fb = wexford_fee_sample()
    assert FeeBreakdown.model_validate(json.loads(fb.model_dump_json())) == fb
