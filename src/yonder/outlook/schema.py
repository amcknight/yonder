"""ReserveExtract — the reserve-focused tool-use schema the model fills from a
depreciation report. Distinct from the general StrataExtract: this is what the
ONE intelligence call returns, and it maps cleanly onto the ReserveOutlook
contract. All monetary values are CAD dollars; all fields nullable except an
expenditure's label (a cost with no name is useless). Absence is first-class:
the model leaves a field null rather than inventing.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, Field


class ProjectedExpenditure(BaseModel):
    label: str                                # the component, e.g. "Roof", "Envelope"
    amount: float | None = None               # projected cost, dollars
    year: int | None = None                   # a point expenditure
    start_year: int | None = None             # or a phased range
    end_year: int | None = None


class ReserveExtract(BaseModel):
    building_name: str | None = None
    report_date: datetime.date | None = None
    current_crf_balance: float | None = None      # opening CRF balance the forecast builds on
    balance_as_of_date: datetime.date | None = None
    recommended_annual_contribution: float | None = None
    funding_model: str | None = None              # free text, e.g. "full funding"
    interest_or_inflation_rate: float | None = None  # the assumption the report uses, if stated
    projected_expenditures: list[ProjectedExpenditure] = Field(default_factory=list)
