"""Prompt + extraction orchestration: validate -> repair-retry-once -> fail loudly."""

from __future__ import annotations

from pydantic import ValidationError

from yonder.extract.schema import StrataExtract

TOOL_NAME = "record_strata_facts"

SYSTEM_PROMPT = """You read British Columbia strata documents and extract structured \
facts for a home-buyer's strata-health view. Rules:

- Extract ONLY what the document states. If a fact is not present, leave it null. \
Never guess or infer a number that is not written.
- A single PDF may be a combined package of several sub-documents (years of AGM \
minutes, a depreciation report, Form B). Populate `documents` with each sub-document \
you identify.
- For every fact, set provenance.page to the page it came from, and provenance.confidence \
to high/medium/low based on how explicit the source is.
- If a document type is not in the known list, use type "other" and put a short label \
in type_label.
- Cost-share / unit-entitlement is a ratio like 18/2719 (this unit / total).

Call the record_strata_facts tool with everything you found."""


def strata_tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Record the structured strata facts extracted from the document.",
        "input_schema": StrataExtract.model_json_schema(),
    }


def extract_strata(pdf_bytes: bytes, *, client) -> StrataExtract:
    """Extract a StrataExtract from PDF bytes. Retries once with the validation
    error fed back to the model; raises ValidationError if the second try is
    also invalid."""
    tool = strata_tool()
    extra_note: str | None = None
    last_error: ValidationError | None = None

    for attempt in range(2):
        raw = client.extract_with_tool(
            pdf_bytes=pdf_bytes,
            system=SYSTEM_PROMPT,
            tool=tool,
            tool_name=TOOL_NAME,
            extra_note=extra_note,
        )
        try:
            return StrataExtract.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            extra_note = (
                "Your previous tool call failed schema validation with these errors:\n"
                f"{exc}\n"
                "Return the record_strata_facts tool call again, corrected. Use null for "
                "anything you are unsure of, and only the allowed enum values."
            )

    assert last_error is not None
    raise last_error
