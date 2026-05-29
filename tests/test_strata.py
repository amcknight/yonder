import pytest
from pydantic import ValidationError

from yonder.extract.schema import StrataExtract
from yonder.extract.strata import extract_strata, strata_tool


def test_strata_tool_has_object_schema():
    tool = strata_tool()
    assert tool["name"] == "record_strata_facts"
    assert tool["input_schema"]["type"] == "object"


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def extract_with_tool(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_valid_first_response_returns_extract():
    client = _FakeClient([{"building": {"name": "Gardens at Yaletown"}}])
    extract = extract_strata(b"%PDF fake", client=client)
    assert isinstance(extract, StrataExtract)
    assert extract.building.name == "Gardens at Yaletown"
    assert len(client.calls) == 1


def test_invalid_then_valid_triggers_one_repair_retry():
    client = _FakeClient(
        [
            {"documents": [{"type": "tax_return"}]},  # invalid enum -> ValidationError
            {"building": {"name": "Recovered"}},      # repaired
        ]
    )
    extract = extract_strata(b"%PDF fake", client=client)
    assert extract.building.name == "Recovered"
    assert len(client.calls) == 2
    assert client.calls[1]["extra_note"] is not None


def test_invalid_twice_fails_loudly():
    client = _FakeClient(
        [
            {"documents": [{"type": "tax_return"}]},
            {"documents": [{"type": "still_bad"}]},
        ]
    )
    with pytest.raises(ValidationError):
        extract_strata(b"%PDF fake", client=client)
    assert len(client.calls) == 2
