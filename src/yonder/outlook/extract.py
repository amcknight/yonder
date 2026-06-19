"""The ONE intelligence call: a depreciation-report PDF -> ReserveExtract.

Forwards to ClaudeClient.extract_validated (the shared retry+repair seam).
Only the system prompt and repair hint are depreciation-report-specific.
"""

from __future__ import annotations

from yonder.outlook.schema import ReserveExtract

TOOL_NAME = "record_reserve_facts"

SYSTEM_PROMPT = """You read a British Columbia strata DEPRECIATION REPORT (a \
30-year contingency-reserve-fund forecast) and extract the facts needed to chart \
the reserve fund's future. Rules:

- Extract ONLY what the report states. If a fact is not present, leave it null. \
Never invent or infer a number that is not written.
- `current_crf_balance` is the opening contingency-reserve-fund balance the \
forecast is built on (with `balance_as_of_date`).
- `recommended_annual_contribution` is the report's recommended annual CRF \
contribution. `funding_model` is the scenario name if given (e.g. "full \
funding", "threshold funding", "cash-flow funding").
- `interest_rate` is the annual return the model assumes ON the CRF balance; \
`inflation_rate` is the annual cost-escalation it assumes ON expenditures. These \
are different numbers — capture each only if the report states it. Express BOTH \
as decimal fractions, NOT percentages (1.8% -> 0.018, 3.0% -> 0.03).
- `projected_expenditures` is the financial forecast / expenditure schedule: one \
entry per major component (roof, envelope, elevators, plumbing, etc.) with its \
projected cost and the year it falls due. Use `year` for a single year, or \
`start_year`/`end_year` for phased work spanning years.

Call the record_reserve_facts tool with everything you found."""

REPAIR_HINT = (
    "Return the record_reserve_facts tool call again, corrected. Use null "
    "for anything the report does not state; every expenditure needs a label."
)

_TOOL_DESCRIPTION = "Record the reserve-fund facts extracted from the depreciation report."


def extract_reserve(pdf_bytes: bytes, *, client) -> ReserveExtract:
    """Extract a ReserveExtract from a depreciation-report PDF (text + page
    images)."""
    return client.extract_validated(
        schema=ReserveExtract,
        tool_name=TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        system=SYSTEM_PROMPT,
        repair_hint=REPAIR_HINT,
        pdf_bytes=pdf_bytes,
    )


def extract_reserve_from_text(text: str, *, client) -> ReserveExtract:
    """Extract a ReserveExtract from a report's already-parsed text (cheaper: no
    page images). Same prompt and repair loop as the PDF path."""
    return client.extract_validated(
        schema=ReserveExtract,
        tool_name=TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        system=SYSTEM_PROMPT,
        repair_hint=REPAIR_HINT,
        text=text,
    )
