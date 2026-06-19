"""Strata-extraction wiring: schema + prompts + the one client call."""

from __future__ import annotations

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

REPAIR_HINT = (
    "Return the record_strata_facts tool call again, corrected. Use null for "
    "anything you are unsure of, and only the allowed enum values."
)

_TOOL_DESCRIPTION = "Record the structured strata facts extracted from the document."


def extract_strata(pdf_bytes: bytes, *, client) -> StrataExtract:
    """Extract a StrataExtract from PDF bytes. Retries once with the validation
    error fed back to the model; raises ValidationError if the second try is
    also invalid."""
    return client.extract_validated(
        schema=StrataExtract,
        tool_name=TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        system=SYSTEM_PROMPT,
        repair_hint=REPAIR_HINT,
        pdf_bytes=pdf_bytes,
    )
