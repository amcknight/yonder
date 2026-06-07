import pytest
from pydantic import ValidationError

from yonder.fees.extract import (
    TOOL_NAME,
    extract_fees,
    extract_fees_from_text,
    fees_tool,
)


class FakeClient:
    """Returns canned tool-input dicts in order; records each call's kwargs."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def test_fees_tool_shape():
    t = fees_tool()
    assert t["name"] == TOOL_NAME == "record_fee_facts"
    assert "input_schema" in t and t["input_schema"]["type"] == "object"


def test_extract_fees_returns_validated():
    fc = FakeClient([{
        "building_name": "X",
        "fiscal_year": 2024,
        "operating_budget": [
            {"label": "Insurance", "parent_category": "Insurance", "annual_amount": 182000},
        ],
        "fee_schedule": [{"lot_id": "1802", "operating_monthly": 521, "crf_monthly": 78}],
    }])
    res = extract_fees(b"%PDF fake", client=fc)
    assert res.building_name == "X"
    assert res.operating_budget[0].parent_category == "Insurance"
    assert res.fee_schedule[0].lot_id == "1802"
    assert len(fc.calls) == 1


def test_extract_fees_repairs_once_then_succeeds():
    bad = {"operating_budget": [{"annual_amount": 1}]}  # missing label + parent_category
    good = {"building_name": "Y", "operating_budget": []}
    fc = FakeClient([bad, good])
    res = extract_fees(b"%PDF fake", client=fc)
    assert res.building_name == "Y"
    assert len(fc.calls) == 2
    assert fc.calls[0]["extra_note"] is None
    assert fc.calls[1]["extra_note"]


def test_extract_fees_raises_if_both_attempts_invalid():
    bad = {"operating_budget": [{"annual_amount": 1}]}
    fc = FakeClient([bad, bad])
    with pytest.raises(ValidationError):
        extract_fees(b"%PDF fake", client=fc)


def test_extract_fees_from_text_passes_text_not_pdf():
    fc = FakeClient([{"building_name": "Z", "operating_budget": []}])
    res = extract_fees_from_text("some parsed budget text", client=fc)
    assert res.building_name == "Z"
    assert fc.calls[0]["text"] == "some parsed budget text"
    assert "pdf_bytes" not in fc.calls[0]
