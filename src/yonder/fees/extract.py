"""The ONE intelligence call: an AGM-package PDF -> FeeExtract.

Forwards to ClaudeClient.extract_validated (the shared retry+repair seam).
Only the system prompt and repair hint are fee-specific.
"""

from __future__ import annotations

from yonder.fees.schema import FeeExtract

TOOL_NAME = "record_fee_facts"

SYSTEM_PROMPT = """You read a British Columbia strata AGM package and extract the \
two facts needed to break down a unit's strata fee. Rules:

- Extract ONLY what the documents state. If a fact is not present, leave it null. \
Never invent or infer a number that is not written.
- `operating_budget` is the APPROVED ANNUAL OPERATING BUDGET: one entry per line \
item, with its account `label`, its budgeted `annual_amount`, and the `fiscal_year` \
the budget is for. For EACH line item also assign a `parent_category` — a short \
rollup bucket. Prefer this vocabulary: "Utilities", "Repairs & maintenance", \
"Insurance", "Security & life-safety", "Building services", "Administration". The \
annual contribution to the contingency reserve fund (a "transfer to CRF" / \
"reserve contribution" line) MUST use the exact parent_category "Reserve \
contribution". If a line fits none of these, use "Other" — never force-fit and \
never drop it.
- `fee_schedule` is the PER-LOT STRATA-FEE SCHEDULE: one entry per strata lot, \
with its `lot_id`, its unit `entitlement`, and its monthly fee split into the \
`operating_monthly` (operating fund) and `crf_monthly` (contingency reserve fund) \
contributions.
- `fiscal_year` (top level) is the budget's fiscal year.

Call the record_fee_facts tool with everything you found."""

REPAIR_HINT = (
    "Return the record_fee_facts tool call again, corrected. Use null for "
    "anything the documents do not state; every budget line needs a label and "
    "a parent_category, and every lot needs a lot_id."
)

_TOOL_DESCRIPTION = "Record the operating budget and per-lot fee schedule from the AGM package."


def extract_fees(pdf_bytes: bytes, *, client) -> FeeExtract:
    """Extract a FeeExtract from an AGM-package PDF (text + page images)."""
    return client.extract_validated(
        schema=FeeExtract,
        tool_name=TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        system=SYSTEM_PROMPT,
        repair_hint=REPAIR_HINT,
        pdf_bytes=pdf_bytes,
    )


def extract_fees_from_text(text: str, *, client) -> FeeExtract:
    """Extract a FeeExtract from already-parsed text (cheaper: no page images)."""
    return client.extract_validated(
        schema=FeeExtract,
        tool_name=TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        system=SYSTEM_PROMPT,
        repair_hint=REPAIR_HINT,
        text=text,
    )
