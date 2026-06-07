"""FeeExtract — the fee-breakdown extraction tool-use schema the model fills from
an AGM package (the approved operating budget + the per-lot strata-fee schedule).

Distinct from StrataExtract and ReserveExtract: this is what the ONE intelligence
call returns for the Fee Breakdown view, and it maps cleanly onto the FeeBreakdown
contract. All monetary values are CAD dollars. All fields nullable except a budget
line's `label` and `parent_category` (the rollup needs both) and a lot's `lot_id`
(the personal-share lookup needs it). Absence is first-class: the model leaves a
field null rather than inventing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BudgetLineItem(BaseModel):
    label: str                          # the account name, e.g. "Water & sewer", "Insurance"
    parent_category: str                # the model's proposed rollup bucket, e.g. "Utilities"
    annual_amount: float | None = None  # budgeted annual dollars
    fiscal_year: int | None = None      # the budget year this line belongs to


class LotFee(BaseModel):
    lot_id: str                              # the strata-lot identifier, e.g. "1802"
    entitlement: int | None = None           # unit entitlement (share of common property)
    operating_monthly: float | None = None   # monthly operating-fund contribution, dollars
    crf_monthly: float | None = None         # monthly contingency-reserve-fund contribution, dollars


class FeeExtract(BaseModel):
    building_name: str | None = None
    fiscal_year: int | None = None                           # the budget's fiscal year
    operating_budget: list[BudgetLineItem] = Field(default_factory=list)
    fee_schedule: list[LotFee] = Field(default_factory=list)
