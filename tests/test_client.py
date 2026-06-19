from unittest.mock import MagicMock

import pytest

from yonder.extract.client import ClaudeClient


def _fake_tool_response(tool_input):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "record_strata_facts"
    block.input = tool_input
    message = MagicMock()
    message.content = [block]
    return message


def test_extract_with_tool_returns_tool_input():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({"building": {"name": "X"}})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    result = client.extract_with_tool(
        pdf_bytes=b"%PDF-1.4 fake",
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
    )

    assert result == {"building": {"name": "X"}}


def test_extract_with_tool_sends_pdf_document_block():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    client.extract_with_tool(
        pdf_bytes=b"%PDF-1.4 fake",
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
    )

    kwargs = sdk.messages.create.call_args.kwargs
    blocks = kwargs["messages"][0]["content"]
    doc_block = next(b for b in blocks if b["type"] == "document")
    assert doc_block["source"]["media_type"] == "application/pdf"
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_strata_facts"}


def test_extra_note_added_as_text_block_in_single_user_message():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    client.extract_with_tool(
        pdf_bytes=b"%PDF-1.4 fake",
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
        extra_note="Your previous output failed validation: bad date.",
    )

    kwargs = sdk.messages.create.call_args.kwargs
    assert len(kwargs["messages"]) == 1
    texts = [b["text"] for b in kwargs["messages"][0]["content"] if b["type"] == "text"]
    assert any("failed validation" in t for t in texts)


def test_extract_with_tool_sends_text_block_when_given_text():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_tool_response({})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    client.extract_with_tool(
        system="sys",
        tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
        tool_name="record_strata_facts",
        text="ROOF replacement 2028 $180,000",
    )

    blocks = sdk.messages.create.call_args.kwargs["messages"][0]["content"]
    assert all(b["type"] != "document" for b in blocks)  # no PDF page-images
    assert any(b["type"] == "text" and "ROOF replacement" in b["text"] for b in blocks)


def test_extract_with_tool_requires_exactly_one_source():
    client = ClaudeClient(sdk=MagicMock(), model="claude-opus-4-8")
    tool = {"name": "t", "input_schema": {"type": "object"}}
    with pytest.raises(ValueError):
        client.extract_with_tool(system="s", tool=tool, tool_name="t")  # neither
    with pytest.raises(ValueError):
        client.extract_with_tool(system="s", tool=tool, tool_name="t",
                                 pdf_bytes=b"x", text="y")  # both


from pydantic import BaseModel
from yonder.extract.client import ClaudeClient


class _ToyExtract(BaseModel):
    name: str
    count: int


def _fake_typed_response(tool_input, tool_name="record_toy"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    message = MagicMock()
    message.content = [block]
    message.stop_reason = "tool_use"
    return message


def test_extract_validated_returns_validated_on_first_try():
    sdk = MagicMock()
    sdk.messages.create.return_value = _fake_typed_response({"name": "X", "count": 3})
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    result = client.extract_validated(
        schema=_ToyExtract,
        tool_name="record_toy",
        tool_description="record toy facts",
        system="sys",
        repair_hint="every toy needs a name and count.",
        pdf_bytes=b"%PDF-1.4 fake",
    )

    assert isinstance(result, _ToyExtract)
    assert result.name == "X" and result.count == 3
    assert sdk.messages.create.call_count == 1


def test_extract_validated_repairs_once_then_succeeds():
    sdk = MagicMock()
    sdk.messages.create.side_effect = [
        _fake_typed_response({"name": "X"}),                # missing count -> ValidationError
        _fake_typed_response({"name": "Y", "count": 7}),    # repaired
    ]
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    result = client.extract_validated(
        schema=_ToyExtract,
        tool_name="record_toy",
        tool_description="record toy facts",
        system="sys",
        repair_hint="every toy needs a name and count.",
        pdf_bytes=b"%PDF-1.4 fake",
    )

    assert result.name == "Y" and result.count == 7
    assert sdk.messages.create.call_count == 2
    second_call_blocks = sdk.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
    repair_texts = [b["text"] for b in second_call_blocks if b["type"] == "text"]
    assert any("failed schema validation" in t for t in repair_texts)
    assert any("every toy needs a name and count." in t for t in repair_texts)


def test_extract_validated_raises_when_both_attempts_invalid():
    from pydantic import ValidationError

    sdk = MagicMock()
    sdk.messages.create.side_effect = [
        _fake_typed_response({"name": "X"}),
        _fake_typed_response({"name": "Y"}),  # still missing count
    ]
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    with pytest.raises(ValidationError):
        client.extract_validated(
            schema=_ToyExtract,
            tool_name="record_toy",
            tool_description="record toy facts",
            system="sys",
            repair_hint="every toy needs a name and count.",
            pdf_bytes=b"%PDF-1.4 fake",
        )
    assert sdk.messages.create.call_count == 2
