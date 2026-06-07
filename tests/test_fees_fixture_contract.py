"""Guards the JSON<->mock seam: the committed fixture must carry every field the
mock (docs/mockups/fee-breakdown.html) derives its render from."""

import json
from pathlib import Path

FIXTURE = Path("fixtures/samples/fee_breakdown.sample.json")


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_exists_and_parses():
    assert FIXTURE.exists(), "run: yonder fees-sample"
    _load()


def test_building_and_unit_meta_present():
    fb = _load()
    assert fb["building"]["name"]
    assert fb["building"]["unit_label"]
    u = fb["unit"]
    assert u["operating_fee_monthly"] and u["reserve_fee_monthly"] and u["total_fee_monthly"]


def test_reserve_row_present_with_building_and_personal():
    r = _load()["reserve"]
    assert r is not None
    assert r["category"] == "Reserve contribution"
    assert r["building_annual"] is not None and r["personal_monthly"] is not None


def test_categories_sorted_with_building_personal_and_line_items():
    cats = _load()["categories"]
    assert cats
    annuals = [c["building_annual"] for c in cats]
    assert annuals == sorted(annuals, reverse=True)
    for c in cats:
        assert c["building_annual"] is not None
        assert c["personal_monthly"] is not None
        assert "line_items" in c
    assert any(len(c["line_items"]) > 1 for c in cats), "need an expandable category for the tap demo"


def test_total_fee_series_has_a_point():
    series = _load()["total_fee_series"]
    assert series and series[-1]["monthly_fee"] is not None
