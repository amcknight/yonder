import datetime
import json

import pytest
from pydantic import ValidationError

from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract


def test_empty_extract_is_valid():
    e = ReserveExtract()
    assert e.projected_expenditures == []
    assert e.current_crf_balance is None


def test_point_and_range_expenditures():
    point = ProjectedExpenditure(label="Roof", amount=180000, year=2028)
    rng = ProjectedExpenditure(label="Envelope", amount=1100000, start_year=2031, end_year=2033)
    assert point.year == 2028 and point.start_year is None
    assert rng.start_year == 2031 and rng.end_year == 2033


def test_parses_iso_dates_and_round_trips():
    e = ReserveExtract(
        building_name="The Spectrum",
        report_date="2022-05-01",
        current_crf_balance=350000,
        balance_as_of_date="2022-05-01",
        recommended_annual_contribution=90000,
        funding_model="full funding",
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=180000, year=2028)],
    )
    assert e.report_date == datetime.date(2022, 5, 1)
    back = ReserveExtract.model_validate(json.loads(e.model_dump_json()))
    assert back == e


def test_label_is_required_on_expenditure():
    with pytest.raises(ValidationError):
        ProjectedExpenditure(amount=180000, year=2028)
