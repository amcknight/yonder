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
