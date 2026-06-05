import json
from pathlib import Path

from yonder.cli import main
from yonder.outlook.model import ReserveOutlook
from yonder.outlook.sample import wexford_sample


def test_wexford_sample_validates_and_has_expected_shape():
    o = wexford_sample()
    assert isinstance(o, ReserveOutlook)
    assert o.unit.entitlement_denominator == 2719
    assert o.start_balance == 420000
    ranged = [e for e in o.expenditures if e.start_year is not None]
    points = [e for e in o.expenditures if e.year is not None]
    assert len(ranged) == 1 and ranged[0].label == "Envelope"
    assert len(points) == 4
    assert any(e.cluster_items for e in o.events)


def test_sample_round_trips_through_plain_json():
    o = wexford_sample()
    blob = o.model_dump_json()
    assert ReserveOutlook.model_validate(json.loads(blob)) == o


def test_outlook_sample_cli_writes_valid_json(tmp_path: Path):
    out = tmp_path / "sample.json"
    rc = main(["outlook-sample", str(out)])
    assert rc == 0
    loaded = ReserveOutlook.model_validate_json(out.read_text())
    assert loaded == wexford_sample()
