"""The ONE intelligence call: a depreciation-report PDF -> ReserveExtract.

Mirrors extract/strata.py: build a forced tool from the Pydantic schema, send
the whole PDF through the client.py Claude seam, and validate ->
repair-retry-once -> fail loudly. This call is kept generic (one PDF -> facts)
so it can later be pointed at any document type, not just depreciation reports.
"""

from __future__ import annotations

from pydantic import ValidationError

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
are different numbers — capture each only if the report states it.
- `projected_expenditures` is the financial forecast / expenditure schedule: one \
entry per major component (roof, envelope, elevators, plumbing, etc.) with its \
projected cost and the year it falls due. Use `year` for a single year, or \
`start_year`/`end_year` for phased work spanning years.

Call the record_reserve_facts tool with everything you found."""


def reserve_tool() -> dict:
    return {
        "name": TOOL_NAME,
        "description": "Record the reserve-fund facts extracted from the depreciation report.",
        "input_schema": ReserveExtract.model_json_schema(),
    }


def extract_reserve(pdf_bytes: bytes, *, client) -> ReserveExtract:
    """Extract a ReserveExtract from PDF bytes. Retries once with the validation
    error fed back to the model; raises ValidationError if the retry is also
    invalid."""
    tool = reserve_tool()
    extra_note: str | None = None
    last_error: ValidationError | None = None

    for _ in range(2):
        raw = client.extract_with_tool(
            pdf_bytes=pdf_bytes,
            system=SYSTEM_PROMPT,
            tool=tool,
            tool_name=TOOL_NAME,
            extra_note=extra_note,
        )
        try:
            return ReserveExtract.model_validate(raw)
        except ValidationError as exc:
            last_error = exc
            extra_note = (
                "Your previous tool call failed schema validation with these errors:\n"
                f"{exc}\n"
                "Return the record_reserve_facts tool call again, corrected. Use null "
                "for anything the report does not state; every expenditure needs a label."
            )

    assert last_error is not None
    raise last_error
