import pytest

from yonder.outlook.assemble import PLACEHOLDER_UNIT, assemble
from yonder.outlook.model import ReserveOutlook
from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract


def _full_extract():
    return ReserveExtract(
        building_name="The Spectrum",
        report_date="2022-05-01",
        current_crf_balance=350000,
        balance_as_of_date="2022-05-01",
        recommended_annual_contribution=90000,
        funding_model="full funding",
        projected_expenditures=[
            ProjectedExpenditure(label="Roof", amount=180000, year=2028),
            ProjectedExpenditure(label="Envelope", amount=1100000, start_year=2031, end_year=2033),
        ],
    )


def test_assemble_maps_real_fields():
    o = assemble(_full_extract())
    assert isinstance(o, ReserveOutlook)
    assert o.degraded is False
    assert o.start_balance == 350000
    assert o.building.name == "The Spectrum"
    assert o.assumptions.base_annual_contribution == 90000
    assert o.assumptions.sourced is True
    assert o.assumptions.interest_rate == 0.02  # placeholder when report states none


def test_assemble_normalizes_percent_interest_rate_to_fraction():
    # The model sometimes returns 1.8 (percent) instead of 0.018 (fraction).
    e = ReserveExtract(
        current_crf_balance=350000,
        interest_rate=1.8,
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=1, year=2028)],
    )
    assert assemble(e).assumptions.interest_rate == pytest.approx(0.018)


def test_assemble_keeps_fractional_interest_rate_as_is():
    e = ReserveExtract(
        current_crf_balance=350000,
        interest_rate=0.025,
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=1, year=2028)],
    )
    assert assemble(e).assumptions.interest_rate == 0.025


def test_assemble_collapses_expenditures_to_points_on_the_timeline():
    o = assemble(_full_extract())
    years = sorted(e.year for e in o.expenditures)
    assert years == [2028, 2031]
    assert all(e.start_year is None for e in o.expenditures)


def test_assemble_derives_projection_window():
    o = assemble(_full_extract())
    assert o.assumptions.projection_start_year == 2022   # from balance_as_of_date
    assert o.assumptions.horizon_end_year == 2031        # latest expenditure


def test_assemble_derives_work_events_alternating_rows():
    o = assemble(_full_extract())
    assert [e.type for e in o.events] == ["work", "work"]
    assert [e.row for e in o.events] == [0, 1]
    assert o.events[0].label.startswith("Roof")
    assert "1.1M" in o.events[1].label
    assert "180k" in o.events[0].label   # sub-$1M formats as $Nk


def test_assemble_uses_placeholder_unit():
    o = assemble(_full_extract())
    assert o.unit == PLACEHOLDER_UNIT
    assert "placeholder" in (o.building.source_note or "")


def test_assemble_degrades_when_no_balance_or_no_expenditures():
    no_bal = ReserveExtract(building_name="B", report_date="2022-01-01",
                            projected_expenditures=[ProjectedExpenditure(label="Roof", amount=1, year=2028)])
    o1 = assemble(no_bal)
    assert o1.degraded is True and "balance" in o1.degraded_reason

    no_exp = ReserveExtract(building_name="B", current_crf_balance=350000)
    o2 = assemble(no_exp)
    assert o2.degraded is True and "expenditure" in o2.degraded_reason
    assert o2.start_balance == 350000  # present-state still carried


def test_assemble_derives_start_from_earliest_expenditure_when_no_dates():
    e = ReserveExtract(
        current_crf_balance=350000,
        projected_expenditures=[
            ProjectedExpenditure(label="Roof", amount=180000, year=2028),
            ProjectedExpenditure(label="Elev", amount=240000, year=2035),
        ],
    )
    o = assemble(e)
    assert o.degraded is False
    assert o.assumptions.projection_start_year == 2028  # earliest expenditure, no dates given
    assert o.assumptions.horizon_end_year == 2035
