import pytest
from pydantic import ValidationError

from yonder.outlook.extract import (
    TOOL_NAME,
    extract_reserve,
    extract_reserve_from_text,
    reserve_tool,
)


class FakeClient:
    """Returns canned tool-input dicts in order; records each call's kwargs."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_reserve_tool_shape():
    t = reserve_tool()
    assert t["name"] == TOOL_NAME == "record_reserve_facts"
    assert "input_schema" in t and t["input_schema"]["type"] == "object"


def test_extract_reserve_returns_validated():
    fc = FakeClient([{
        "building_name": "X",
        "current_crf_balance": 350000,
        "projected_expenditures": [{"label": "Roof", "amount": 180000, "year": 2028}],
    }])
    res = extract_reserve(b"%PDF fake", client=fc)
    assert res.building_name == "X"
    assert res.projected_expenditures[0].label == "Roof"
    assert len(fc.calls) == 1


def test_extract_reserve_repairs_once_then_succeeds():
    bad = {"projected_expenditures": [{"amount": 180000}]}      # missing required label
    good = {"building_name": "Y", "projected_expenditures": []}
    fc = FakeClient([bad, good])
    res = extract_reserve(b"%PDF fake", client=fc)
    assert res.building_name == "Y"
    assert len(fc.calls) == 2
    assert fc.calls[0]["extra_note"] is None   # first attempt carries no repair note
    assert fc.calls[1]["extra_note"]  # the repair note was sent on the retry


def test_extract_reserve_raises_if_both_attempts_invalid():
    bad = {"projected_expenditures": [{"amount": 180000}]}      # missing required label
    fc = FakeClient([bad, bad])
    with pytest.raises(ValidationError):
        extract_reserve(b"%PDF fake", client=fc)


def test_extract_reserve_from_text_passes_text_not_pdf():
    fc = FakeClient([{
        "building_name": "Z",
        "current_crf_balance": 900000,
        "projected_expenditures": [{"label": "Roof", "amount": 180000, "year": 2028}],
    }])
    res = extract_reserve_from_text("some parsed report text", client=fc)
    assert res.building_name == "Z"
    assert fc.calls[0]["text"] == "some parsed report text"
    assert "pdf_bytes" not in fc.calls[0]
