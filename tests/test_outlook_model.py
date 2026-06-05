import json

import pytest
from pydantic import ValidationError

from yonder.outlook.model import (
    Assumptions,
    BalancePoint,
    Expenditure,
    PlannedFeeChange,
    ReserveOutlook,
    TimelineEvent,
    Unit,
)


def test_empty_outlook_is_valid_and_degraded_defaults_false():
    """Absence is first-class: an all-empty outlook must validate."""
    o = ReserveOutlook()
    assert o.expenditures == []
    assert o.history == []
    assert o.degraded is False
    assert o.start_balance is None


def test_degraded_outlook_carries_a_reason():
    o = ReserveOutlook(degraded=True, degraded_reason="no current depreciation report")
    assert o.degraded is True
    assert o.degraded_reason == "no current depreciation report"


def test_point_and_range_expenditures():
    point = Expenditure(label="Roof", amount=180000, year=2028)
    rng = Expenditure(label="Envelope", amount=1100000, start_year=2031, end_year=2033, peak_year=2032)
    assert point.year == 2028 and point.start_year is None
    assert rng.start_year == 2031 and rng.peak_year == 2032


def test_event_allows_fractional_year_and_cluster_items():
    ev = TimelineEvent(year=2027.75, row=1, type="fee", label="+10% plan")
    cluster = TimelineEvent(year=2030, row=1, type="meeting", cluster_items=["a", "b"])
    assert ev.year == 2027.75
    assert cluster.cluster_items == ["a", "b"]


def test_planned_fee_change_pct_is_fraction():
    f = PlannedFeeChange(effective_year=2028, pct=0.10)
    assert f.pct == 0.10


def test_full_outlook_round_trips_through_json():
    o = ReserveOutlook(
        unit=Unit(entitlement_numerator=18, entitlement_denominator=2719, strata_fee_monthly=486),
        assumptions=Assumptions(base_annual_contribution=90000, history_start_year=2020,
                                projection_start_year=2026, horizon_end_year=2041),
        start_balance=420000,
        history=[BalancePoint(year=2020, balance=260000)],
        expenditures=[Expenditure(label="Roof", amount=180000, year=2028)],
        planned_fee_changes=[PlannedFeeChange(effective_year=2028, pct=0.10)],
        events=[TimelineEvent(year=2028, row=0, type="work", label="Roof 180k")],
    )
    blob = o.model_dump_json()
    back = ReserveOutlook.model_validate_json(blob)
    assert back == o
    assert ReserveOutlook.model_validate(json.loads(blob)) == o
