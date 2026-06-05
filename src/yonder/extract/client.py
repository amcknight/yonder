"""Thin Claude seam. The ONE file to change when swapping to Bedrock.

Builds a forced tool-use request with the PDF as a base64 document block and
returns the tool's input dict.
"""

from __future__ import annotations

import base64
import os


class ExtractionError(RuntimeError):
    """The model did not return the expected tool call."""


class ClaudeClient:
    def __init__(self, *, sdk=None, api_key: str | None = None, model: str = "claude-opus-4-8"):
        if sdk is None:
            from anthropic import Anthropic

            sdk = Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])
        self._sdk = sdk
        self.model = model

    def extract_with_tool(
        self,
        *,
        system: str,
        tool: dict,
        tool_name: str,
        pdf_bytes: bytes | None = None,
        text: str | None = None,
        extra_note: str | None = None,
        max_tokens: int = 8000,
    ) -> dict:
        """Send a document to Claude for forced tool-use. Provide exactly one of
        `pdf_bytes` (sent as a PDF document block — text + page images, costlier)
        or `text` (sent as a plain text block — cheaper, no page images)."""
        if (pdf_bytes is None) == (text is None):
            raise ValueError("Provide exactly one of pdf_bytes or text.")
        if text is not None:
            content = [
                {"type": "text", "text": "Document (extracted text) follows:\n\n" + text},
                {"type": "text", "text": "Extract the requested facts from this document."},
            ]
        else:
            b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
            content = [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": b64,
                    },
                },
                {"type": "text", "text": "Extract the strata facts from this document."},
            ]
        if extra_note:
            content.append({"type": "text", "text": extra_note})
        messages = [{"role": "user", "content": content}]

        message = self._sdk.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=messages,
        )
        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return block.input
        raise ExtractionError(f"No '{tool_name}' tool_use block in response.")
