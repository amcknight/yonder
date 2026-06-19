from yonder.extract.schema import StrataExtract
from yonder.extract.strata import REPAIR_HINT, SYSTEM_PROMPT, TOOL_NAME, extract_strata


class _FakeClient:
    """Stubs extract_validated; records each call's kwargs."""

    def __init__(self, response: StrataExtract):
        self._response = response
        self.calls: list[dict] = []

    def extract_validated(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def test_extract_strata_wires_schema_and_constants():
    canned = StrataExtract.model_validate({"building": {"name": "Gardens at Yaletown"}})
    client = _FakeClient(canned)

    result = extract_strata(b"%PDF fake", client=client)

    assert result is canned
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["schema"] is StrataExtract
    assert call["tool_name"] == TOOL_NAME == "record_strata_facts"
    assert call["system"] == SYSTEM_PROMPT
    assert call["repair_hint"] == REPAIR_HINT
    assert call["pdf_bytes"] == b"%PDF fake"
