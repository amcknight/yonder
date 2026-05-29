from unittest.mock import MagicMock

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


def test_extra_note_appended_as_second_message():
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
    assert len(kwargs["messages"]) == 2
    assert "failed validation" in kwargs["messages"][1]["content"]
