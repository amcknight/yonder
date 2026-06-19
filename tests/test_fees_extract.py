from yonder.fees.extract import (
    REPAIR_HINT,
    SYSTEM_PROMPT,
    TOOL_NAME,
    extract_fees,
    extract_fees_from_text,
)
from yonder.fees.schema import FeeExtract


class _FakeClient:
    def __init__(self, response: FeeExtract):
        self._response = response
        self.calls: list[dict] = []

    def extract_validated(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def _canned() -> FeeExtract:
    return FeeExtract.model_validate({
        "building_name": "X",
        "fiscal_year": 2024,
        "operating_budget": [
            {"label": "Insurance", "parent_category": "Insurance", "annual_amount": 182000},
        ],
        "fee_schedule": [{"lot_id": "1802", "operating_monthly": 521, "crf_monthly": 78}],
    })


def test_extract_fees_wires_schema_and_constants_with_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_fees(b"%PDF fake", client=client)

    assert result is canned
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["schema"] is FeeExtract
    assert call["tool_name"] == TOOL_NAME == "record_fee_facts"
    assert call["system"] == SYSTEM_PROMPT
    assert call["repair_hint"] == REPAIR_HINT
    assert call["pdf_bytes"] == b"%PDF fake"
    assert "text" not in call


def test_extract_fees_from_text_sends_text_not_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_fees_from_text("parsed budget text", client=client)

    assert result is canned
    assert client.calls[0]["text"] == "parsed budget text"
    assert "pdf_bytes" not in client.calls[0]
