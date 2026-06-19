# Consolidate Extraction-Call Plumbing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoist the validate→repair-retry-once loop and the tool-spec construction out of three subsystem modules and into `ClaudeClient`, then enrich the client's error surfaces with debuggable context.

**Architecture:** Add one new method `ClaudeClient.extract_validated(schema, tool_name, tool_description, system, repair_hint, **source)` that constructs the Anthropic tool dict from the Pydantic schema, calls the existing `extract_with_tool` low-level method in a 2-iteration loop, and either returns a validated Pydantic model or raises `ValidationError`. Migrate `extract/strata.py`, `outlook/extract.py`, `fees/extract.py` to call it. Bolt observability into the existing `extract_with_tool` so SDK errors and missing-tool_use errors carry context.

**Tech Stack:** Python 3.11+, Pydantic v2, Anthropic Python SDK, pytest. `uv` invoked as `python -m uv` per env-yonder-tooling.

## Global Constraints

- Preserve existing public function signatures: `extract_strata(pdf_bytes, *, client) -> StrataExtract`, `extract_reserve(pdf_bytes, *, client) -> ReserveExtract`, `extract_reserve_from_text(text, *, client) -> ReserveExtract`, `extract_fees(pdf_bytes, *, client) -> FeeExtract`, `extract_fees_from_text(text, *, client) -> FeeExtract`. CLI calls these — never break them.
- Preserve repair semantics exactly: one repair attempt then raise the last `ValidationError`. Two attempts total, never more.
- Per-subsystem `repair_hint` text must be preserved verbatim (Claude is sensitive to prompt wording). Pass it through as a parameter.
- `ClaudeClient` remains the documented Bedrock seam (the ONE file to change). Don't introduce a new client abstraction.
- `extract_with_tool` remains the low-level "one API call" method. The new `extract_validated` is a convenience wrapper on top.
- Use Python type hints everywhere. `TypeVar` bound to `pydantic.BaseModel` for the schema parameter.
- No new dependencies.

---

## File Structure

**Modify:**
- `src/yonder/extract/client.py` — add `extract_validated` method; enrich `extract_with_tool` error context.
- `src/yonder/extract/strata.py` — replace local loop with `client.extract_validated(...)` call; delete `strata_tool()`.
- `src/yonder/outlook/extract.py` — replace `_run` with `client.extract_validated(...)`; delete `reserve_tool()` and `_run`.
- `src/yonder/fees/extract.py` — replace `_run` with `client.extract_validated(...)`; delete `fees_tool()` and `_run`.

**Modify (tests):**
- `tests/test_client.py` — add tests for `extract_validated` (3 tests) and the enriched `extract_with_tool` error paths (2 tests).
- `tests/test_strata.py` — rewrite `_FakeClient` to stub `extract_validated`; drop the loop tests (now covered at client level).
- `tests/test_reserve_extract.py` — same pattern as test_strata.py.
- `tests/test_fees_extract.py` — same pattern.

**Not modified:** `cli.py` (public extract functions keep their signatures), schemas, all assemble/compute/sample modules, mockups, fixtures.

---

### Task 1: Add `extract_validated` to ClaudeClient

**Files:**
- Modify: `src/yonder/extract/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: existing `extract_with_tool` on `ClaudeClient` (`src/yonder/extract/client.py:26-75`).
- Produces:
  ```python
  T = TypeVar("T", bound=BaseModel)

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
  ) -> T: ...
  ```
  Behavior: builds a tool dict `{name, description, input_schema=schema.model_json_schema()}`, calls `self.extract_with_tool` up to twice. After call 1, attempts `schema.model_validate(raw)`. On `ValidationError`, builds a repair `extra_note` of the form `"Your previous tool call failed schema validation with these errors:\n{exc}\n{repair_hint}"` and re-calls. On second `ValidationError`, raises that error.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_client.py` (after existing tests):

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_client.py -v`
Expected: 3 new tests FAIL with `AttributeError: 'ClaudeClient' object has no attribute 'extract_validated'`. Existing tests still pass.

- [ ] **Step 3: Implement `extract_validated`**

Edit `src/yonder/extract/client.py`. Add imports near the top:

```python
from typing import TypeVar

from pydantic import BaseModel, ValidationError
```

Add a TypeVar after the imports:

```python
T = TypeVar("T", bound=BaseModel)
```

Add the new method on `ClaudeClient` (after the existing `extract_with_tool`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_client.py -v`
Expected: all 8 tests pass (5 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/extract/client.py tests/test_client.py
git commit -m "feat(client): add extract_validated with retry+repair loop"
```

---

### Task 2: Enrich `extract_with_tool` error context

**Files:**
- Modify: `src/yonder/extract/client.py:64-75`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: existing `extract_with_tool` signature (unchanged).
- Produces: same return type, same happy path; richer `ExtractionError` messages on the two failure paths.

**What changes:**
1. Wrap `self._sdk.messages.create(...)` in `try/except Exception as exc:` and re-raise as `ExtractionError` with input mode (`pdf` or `text`) and the first 80 chars of the system prompt.
2. When the no-tool_use raise fires, include `stop_reason` and the list of content-block types in the error message.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_client.py`:

```python
def test_extract_with_tool_wraps_sdk_errors_with_context():
    sdk = MagicMock()
    sdk.messages.create.side_effect = RuntimeError("upstream rate-limited")
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    with pytest.raises(ExtractionError) as excinfo:
        client.extract_with_tool(
            pdf_bytes=b"%PDF-1.4 fake",
            system="You read BC strata documents and extract structured facts.",
            tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
            tool_name="record_strata_facts",
        )

    msg = str(excinfo.value)
    assert "pdf" in msg                      # input mode disclosed
    assert "You read BC strata" in msg       # system-prompt prefix disclosed
    assert "upstream rate-limited" in msg    # underlying error preserved
    assert excinfo.value.__cause__ is not None  # SDK exception chained


def test_extract_with_tool_no_tool_use_error_includes_stop_reason():
    sdk = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    message = MagicMock()
    message.content = [text_block]
    message.stop_reason = "end_turn"
    sdk.messages.create.return_value = message
    client = ClaudeClient(sdk=sdk, model="claude-opus-4-8")

    with pytest.raises(ExtractionError) as excinfo:
        client.extract_with_tool(
            pdf_bytes=b"%PDF-1.4 fake",
            system="sys",
            tool={"name": "record_strata_facts", "input_schema": {"type": "object"}},
            tool_name="record_strata_facts",
        )

    msg = str(excinfo.value)
    assert "record_strata_facts" in msg
    assert "end_turn" in msg          # stop_reason disclosed
    assert "text" in msg              # content-block types disclosed
```

Need to import `ExtractionError` at the top of the test file if it isn't already:

```python
from yonder.extract.client import ClaudeClient, ExtractionError
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_client.py -v`
Expected: 2 new tests FAIL — the first because the RuntimeError bubbles raw (no wrapping), the second because the current `ExtractionError` message has no `stop_reason` or content-block types.

- [ ] **Step 3: Implement the enrichment**

In `src/yonder/extract/client.py`, replace the `messages.create` block and the no-tool_use raise (currently lines 64-75) with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_client.py -v`
Expected: all 10 tests pass (5 existing + 3 from Task 1 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/extract/client.py tests/test_client.py
git commit -m "feat(client): enrich extract_with_tool error context (stop_reason, input mode)"
```

---

### Task 3: Migrate `extract/strata.py` to `extract_validated`

**Files:**
- Modify: `src/yonder/extract/strata.py`
- Modify: `tests/test_strata.py`

**Interfaces:**
- Consumes: `ClaudeClient.extract_validated` from Task 1.
- Produces: `extract_strata(pdf_bytes: bytes, *, client) -> StrataExtract` (unchanged public signature; only the body changes). `strata_tool()` is deleted.

**Heads-up about the test rewrite:** the existing `_FakeClient` in `tests/test_strata.py` stubs `extract_with_tool` and tests the local loop. After migration, the loop lives in `ClaudeClient.extract_validated` (already tested in Task 1). The strata-level tests should now stub `extract_validated` directly and assert that `extract_strata` wires up the right schema/tool_name/system/repair_hint. The repair-loop semantics test moves out of this file (it's covered in test_client.py from Task 1).

- [ ] **Step 1: Write the failing test (new shape)**

Replace the entire contents of `tests/test_strata.py` with:

```python
from yonder.extract.schema import StrataExtract
from yonder.extract.strata import REPAIR_HINT, SYSTEM_PROMPT, TOOL_NAME, extract_strata


class _FakeClient:
    """Stubs extract_validated; records each call's kwargs."""

    def __init__(self, response: StrataExtract):
        self._response = response
        self.calls: list[dict] = []

    def extract_validated(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def test_extract_strata_wires_schema_and_constants():
    canned = StrataExtract.model_validate({"building": {"name": "Gardens at Yaletown"}})
    client = _FakeClient(canned)

    result = extract_strata(b"%PDF fake", client=client)

    assert result is canned
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["schema"] is StrataExtract
    assert call["tool_name"] == TOOL_NAME == "record_strata_facts"
    assert call["system"] == SYSTEM_PROMPT
    assert call["repair_hint"] == REPAIR_HINT
    assert call["pdf_bytes"] == b"%PDF fake"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_strata.py -v`
Expected: FAIL — `REPAIR_HINT` doesn't exist yet; `extract_strata` doesn't call `extract_validated`.

- [ ] **Step 3: Replace `src/yonder/extract/strata.py` body**

Replace the entire file with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_strata.py tests/test_client.py -v`
Expected: all pass. `pydantic` and `ValidationError` are no longer needed in `strata.py` — verify nothing imports them from there (it's safe; they were only used internally).

- [ ] **Step 5: Commit**

```bash
git add src/yonder/extract/strata.py tests/test_strata.py
git commit -m "refactor(extract): migrate strata to ClaudeClient.extract_validated"
```

---

### Task 4: Migrate `outlook/extract.py` to `extract_validated`

**Files:**
- Modify: `src/yonder/outlook/extract.py`
- Modify: `tests/test_reserve_extract.py`

**Interfaces:**
- Consumes: `ClaudeClient.extract_validated` from Task 1.
- Produces: `extract_reserve(pdf_bytes: bytes, *, client) -> ReserveExtract` and `extract_reserve_from_text(text: str, *, client) -> ReserveExtract` (unchanged public signatures). `reserve_tool()` and `_run` are deleted.

- [ ] **Step 1: Write the failing tests (new shape)**

Replace the entire contents of `tests/test_reserve_extract.py` with:

```python
from yonder.outlook.extract import (
    REPAIR_HINT,
    SYSTEM_PROMPT,
    TOOL_NAME,
    extract_reserve,
    extract_reserve_from_text,
)
from yonder.outlook.schema import ReserveExtract


class _FakeClient:
    def __init__(self, response: ReserveExtract):
        self._response = response
        self.calls: list[dict] = []

    def extract_validated(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def _canned() -> ReserveExtract:
    return ReserveExtract.model_validate({
        "building_name": "X",
        "current_crf_balance": 350000,
        "projected_expenditures": [{"label": "Roof", "amount": 180000, "year": 2028}],
    })


def test_extract_reserve_wires_schema_and_constants_with_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_reserve(b"%PDF fake", client=client)

    assert result is canned
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["schema"] is ReserveExtract
    assert call["tool_name"] == TOOL_NAME == "record_reserve_facts"
    assert call["system"] == SYSTEM_PROMPT
    assert call["repair_hint"] == REPAIR_HINT
    assert call["pdf_bytes"] == b"%PDF fake"
    assert "text" not in call


def test_extract_reserve_from_text_sends_text_not_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_reserve_from_text("parsed report text", client=client)

    assert result is canned
    assert client.calls[0]["text"] == "parsed report text"
    assert "pdf_bytes" not in client.calls[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_reserve_extract.py -v`
Expected: FAIL — `REPAIR_HINT` doesn't exist; `extract_reserve` still uses local `_run`.

- [ ] **Step 3: Replace `src/yonder/outlook/extract.py` body**

Replace the entire file with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_reserve_extract.py tests/test_client.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/yonder/outlook/extract.py tests/test_reserve_extract.py
git commit -m "refactor(outlook): migrate extract to ClaudeClient.extract_validated"
```

---

### Task 5: Migrate `fees/extract.py` to `extract_validated`

**Files:**
- Modify: `src/yonder/fees/extract.py`
- Modify: `tests/test_fees_extract.py`

**Interfaces:**
- Consumes: `ClaudeClient.extract_validated` from Task 1.
- Produces: `extract_fees(pdf_bytes: bytes, *, client) -> FeeExtract` and `extract_fees_from_text(text: str, *, client) -> FeeExtract` (unchanged public signatures). `fees_tool()` and `_run` are deleted.

- [ ] **Step 1: Write the failing tests (new shape)**

Replace the entire contents of `tests/test_fees_extract.py` with:

```python
from yonder.fees.extract import (
    REPAIR_HINT,
    SYSTEM_PROMPT,
    TOOL_NAME,
    extract_fees,
    extract_fees_from_text,
)
from yonder.fees.schema import FeeExtract


class _FakeClient:
    def __init__(self, response: FeeExtract):
        self._response = response
        self.calls: list[dict] = []

    def extract_validated(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def _canned() -> FeeExtract:
    return FeeExtract.model_validate({
        "building_name": "X",
        "fiscal_year": 2024,
        "operating_budget": [
            {"label": "Insurance", "parent_category": "Insurance", "annual_amount": 182000},
        ],
        "fee_schedule": [{"lot_id": "1802", "operating_monthly": 521, "crf_monthly": 78}],
    })


def test_extract_fees_wires_schema_and_constants_with_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_fees(b"%PDF fake", client=client)

    assert result is canned
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["schema"] is FeeExtract
    assert call["tool_name"] == TOOL_NAME == "record_fee_facts"
    assert call["system"] == SYSTEM_PROMPT
    assert call["repair_hint"] == REPAIR_HINT
    assert call["pdf_bytes"] == b"%PDF fake"
    assert "text" not in call


def test_extract_fees_from_text_sends_text_not_pdf():
    canned = _canned()
    client = _FakeClient(canned)

    result = extract_fees_from_text("parsed budget text", client=client)

    assert result is canned
    assert client.calls[0]["text"] == "parsed budget text"
    assert "pdf_bytes" not in client.calls[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m uv run pytest tests/test_fees_extract.py -v`
Expected: FAIL — `REPAIR_HINT` doesn't exist; `extract_fees` still uses local `_run`.

- [ ] **Step 3: Replace `src/yonder/fees/extract.py` body**

Replace the entire file with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m uv run pytest tests/test_fees_extract.py tests/test_client.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/yonder/fees/extract.py tests/test_fees_extract.py
git commit -m "refactor(fees): migrate extract to ClaudeClient.extract_validated"
```

---

### Task 6: Full-suite verification

**Files:**
- No new file edits. Verifies the migration didn't break the rest of the suite.

**Interfaces:** none — this is a verification gate.

- [ ] **Step 1: Run the entire test suite**

Run: `python -m uv run pytest -v`
Expected: all tests pass. Live integration test `tests/test_fees_extract_live.py` skips without `ANTHROPIC_API_KEY`.

- [ ] **Step 2: Sanity-check the CLI imports**

Run: `python -m uv run python -c "from yonder.cli import main; from yonder.extract.strata import extract_strata; from yonder.outlook.extract import extract_reserve, extract_reserve_from_text; from yonder.fees.extract import extract_fees, extract_fees_from_text; print('imports OK')"`
Expected: `imports OK` printed; no `ImportError` for the deleted `*_tool` / `_run` symbols.

- [ ] **Step 3: Inspect the final state of `client.py`**

Run: `python -m uv run python -c "from yonder.extract.client import ClaudeClient; c = ClaudeClient.__dict__; print([n for n in c if not n.startswith('_')])"`
Expected: shows `extract_with_tool` and `extract_validated` as public methods.

- [ ] **Step 4: No commit required if Steps 1–3 are clean.** If a test caught something unexpected, fix it in this task and commit.

---

## Self-Review Notes

**Spec coverage:**
- CF1 absorbs A2, A3 → covered by Tasks 1, 3, 4, 5 (loop hoisted; three call sites become one-liners).
- CF1 absorbs C2 → covered by Task 1 (tool dict built once inside `extract_validated`; subsystems no longer hand-roll it).
- CF1 absorbs TC1, TC2 → partially: the three `*_tool() -> dict` factories are deleted (TC2 resolved). `extract_with_tool` still takes a `tool: dict` (TC1 not addressed — left as a future trivial since the only remaining caller is `extract_validated` which builds the dict internally). Acceptable scope cut: TC1's "bare dict" matters less when the dict is now constructed by one well-typed caller.
- CF1 absorbs O1, O2 → covered by Task 2.

**Placeholder scan:** No TBDs, no "implement appropriate handling", every code step shows the actual code. Confirmed.

**Type consistency:**
- New method name `extract_validated` used consistently across Tasks 1, 3, 4, 5.
- Parameter names (`schema`, `tool_name`, `tool_description`, `system`, `repair_hint`, `pdf_bytes`, `text`) consistent across Task 1's signature and the call sites in Tasks 3, 4, 5.
- Module-level constants `TOOL_NAME`, `SYSTEM_PROMPT`, `REPAIR_HINT` consistent across the three subsystems' migrations and the tests that assert on them.

**Risk acknowledged:** The repair hint text is preserved verbatim per subsystem (each module's `REPAIR_HINT` constant contains exactly the suffix that used to appear in its inline `extra_note` formatting). The standard prefix (`"Your previous tool call failed schema validation with these errors:\n{exc}\n"`) is now centralized in `extract_validated`. Result: same final string reaches Claude on the repair turn.
