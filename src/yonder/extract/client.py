"""Thin Claude seam. The ONE file to change when swapping to Bedrock.

Builds a forced tool-use request with the PDF as a base64 document block and
returns the tool's input dict.
"""

from __future__ import annotations

import base64
import os
from typing import TypeVar

from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)


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

        input_mode = "pdf" if pdf_bytes is not None else "text"
        try:
            message = self._sdk.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=messages,
            )
        except Exception as exc:
            raise ExtractionError(
                f"Anthropic API call failed [{input_mode}] (system: {system[:80]!r}): {exc}"
            ) from exc

        for block in message.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return block.input

        block_types = [getattr(b, "type", "?") for b in message.content]
        raise ExtractionError(
            f"No '{tool_name}' tool_use block in response "
            f"(stop_reason={getattr(message, 'stop_reason', None)!r}, "
            f"content_blocks={block_types})."
        )

    def extract_validated(
        self,
        *,
        schema: type[T],
        tool_name: str,
        tool_description: str,
        system: str,
        repair_hint: str,
        pdf_bytes: bytes | None = None,
        text: str | None = None,
        max_tokens: int = 8000,
    ) -> T:
        """Forced tool-use + schema validation + one repair retry. The repair turn
        feeds the ValidationError back to the model with `repair_hint` appended
        (subsystem-specific corrective guidance, e.g. "every budget line needs a
        label"). Raises ValidationError if the second attempt is also invalid."""
        tool = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": schema.model_json_schema(),
        }
        source = {"pdf_bytes": pdf_bytes} if pdf_bytes is not None else {"text": text}
        extra_note: str | None = None
        last_error: ValidationError | None = None

        for _ in range(2):
            raw = self.extract_with_tool(
                system=system,
                tool=tool,
                tool_name=tool_name,
                extra_note=extra_note,
                max_tokens=max_tokens,
                **source,
            )
            try:
                return schema.model_validate(raw)
            except ValidationError as exc:
                last_error = exc
                extra_note = (
                    "Your previous tool call failed schema validation with these errors:\n"
                    f"{exc}\n"
                    f"{repair_hint}"
                )

        assert last_error is not None
        raise last_error
