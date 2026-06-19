from yonder.outlook.extract import (
    REPAIR_HINT,
    SYSTEM_PROMPT,
    TOOL_NAME,
    extract_reserve,
    extract_reserve_from_text,
)
from yonder.outlook.schema import ReserveExtract


class _FakeClient:
    def __init__(self, response: ReserveExtract):
        self._response = response
        self.calls: list[dict] = []

    def extract_validated(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def _canned() -> ReserveExtract:
    return ReserveExtract.model_validate({
        "building_name": "X",
        "current_crf_balance": 350000,
        "projected_expenditures": [{"label": "Roof", "amount": 180000, "year": 2028}],
    })


def test_extract_reserve_wires_schema_and_constants_with_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_reserve(b"%PDF fake", client=client)

    assert result is canned
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["schema"] is ReserveExtract
    assert call["tool_name"] == TOOL_NAME == "record_reserve_facts"
    assert call["system"] == SYSTEM_PROMPT
    assert call["repair_hint"] == REPAIR_HINT
    assert call["pdf_bytes"] == b"%PDF fake"
    assert "text" not in call


def test_extract_reserve_from_text_sends_text_not_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_reserve_from_text("parsed report text", client=client)

    assert result is canned
    assert client.calls[0]["text"] == "parsed report text"
    assert "pdf_bytes" not in client.calls[0]
