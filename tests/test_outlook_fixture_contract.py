"""Guards the JSON<->mock seam: the committed fixture must carry every field the
dashboard (docs/mockups/reserve-trajectory.html) derives its constants from."""

import json
from pathlib import Path

FIXTURE = Path("fixtures/samples/reserve_outlook.sample.json")


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_exists_and_parses():
    assert FIXTURE.exists(), "run: yonder outlook-sample"
    _load()


def test_assumptions_carry_projection_window_and_contribution():
    a = _load()["assumptions"]
    for key in ("base_annual_contribution", "history_start_year",
                "projection_start_year", "horizon_end_year", "interest_rate"):
        assert a[key] is not None, f"assumptions.{key} missing"


def test_unit_carries_entitlement_and_fee():
    u = _load()["unit"]
    assert u["entitlement_numerator"] and u["entitlement_denominator"]
    assert u["strata_fee_monthly"] and u["reserve_portion_monthly"]


def test_has_history_point_expenditures_and_one_range():
    o = _load()
    assert o["start_balance"] is not None
    assert len(o["history"]) >= 2
    assert any(e.get("year") is not None for e in o["expenditures"])
    assert any(e.get("start_year") is not None for e in o["expenditures"])


def test_has_events_including_a_cluster():
    events = _load()["events"]
    assert events
    assert any(e.get("cluster_items") for e in events)


def test_planned_fee_change_pcts_are_fractions_not_percents():
    """Guard the unit semantics the mock relies on: feeFactor does 1 + pct, so
    a percent-as-integer (10 instead of 0.10) would silently 11x contributions."""
    for f in _load()["planned_fee_changes"]:
        assert -1 < f["pct"] < 1, f"pct {f['pct']} looks like a percent, expected a fraction"
