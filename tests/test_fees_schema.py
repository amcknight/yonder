import json

import pytest
from pydantic import ValidationError

from yonder.fees.schema import BudgetLineItem, FeeExtract, LotFee


def test_empty_extract_is_valid():
    e = FeeExtract()
    assert e.operating_budget == []
    assert e.fee_schedule == []
    assert e.building_name is None


def test_budget_line_item_requires_label_and_parent_category():
    with pytest.raises(ValidationError):
        BudgetLineItem(annual_amount=1000)  # no label, no parent_category


def test_lot_fee_requires_lot_id():
    with pytest.raises(ValidationError):
        LotFee(operating_monthly=521)  # no lot_id


def test_round_trips_through_plain_json():
    e = FeeExtract(
        building_name="The Spectrum",
        fiscal_year=2024,
        operating_budget=[
            BudgetLineItem(label="Insurance premium", parent_category="Insurance",
                           annual_amount=182000, fiscal_year=2024),
        ],
        fee_schedule=[
            LotFee(lot_id="1802", entitlement=82, operating_monthly=521, crf_monthly=78),
        ],
    )
    back = FeeExtract.model_validate(json.loads(e.model_dump_json()))
    assert back == e
    assert back.operating_budget[0].parent_category == "Insurance"
    assert back.fee_schedule[0].lot_id == "1802"
