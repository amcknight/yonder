"""Pure mapping: ReserveExtract -> ReserveOutlook (the frozen contract).

Real fields come from the depreciation report; the unit is a documented
placeholder (no Form B in the corpus); balance history is empty (only the
current balance is known) so the mock's "actual" line collapses to the now
point. If the report yields no balance or no datable expenditures, return a
`degraded` present-state outlook rather than a fabricated projection.
"""

from __future__ import annotations

from yonder.outlook.model import (
    Assumptions,
    BuildingMeta,
    Expenditure,
    ReserveOutlook,
    TimelineEvent,
    Unit,
)
from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract

# No Form B in the corpus -> unit figures are illustrative. Mirrors the Wexford
# sample's values for visual continuity; clearly labelled placeholder.
PLACEHOLDER_UNIT = Unit(
    entitlement_numerator=18,
    entitlement_denominator=2719,
    strata_fee_monthly=486,
    reserve_portion_monthly=50,
)

_DEFAULT_HORIZON_YEARS = 30  # fallback projection span when the report gives only one datable year


def _year_of(e: ProjectedExpenditure) -> int | None:
    return e.year if e.year is not None else e.start_year


def _short_amt(amount: float | None) -> str:
    if amount is None:
        return ""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    return f"${round(amount / 1000)}k"


def _source_note(extract: ReserveExtract) -> str:
    yr = extract.report_date.year if extract.report_date else "?"
    return f"deprec. report {yr} · unit figures placeholder"


def _rate_as_fraction(rate: float | None) -> float:
    """Normalize an interest rate to a decimal fraction. Models sometimes return
    the percentage value (1.8 for 1.8%) instead of the fraction (0.018); a real
    CRF rate is never > 1, so treat anything above that as a percent."""
    if rate is None:
        return 0.02
    return rate / 100 if abs(rate) > 1 else rate


def assemble(extract: ReserveExtract, *, unit: Unit = PLACEHOLDER_UNIT) -> ReserveOutlook:
    building = BuildingMeta(
        name=extract.building_name,
        depreciation_report_date=extract.report_date,
        source_note=_source_note(extract),
    )
    # Collapse every expenditure to a single timeline year (the mock renders only
    # one range band; collapsing keeps all expenditures correct in the projection).
    # Collapsing a range to one year also shifts its full cost to that year in the
    # projection itself (a modeling simplification, not only a rendering one).
    points = [
        Expenditure(label=e.label, amount=e.amount if e.amount is not None else 0.0, year=_year_of(e))
        for e in extract.projected_expenditures
        if _year_of(e) is not None
    ]

    if extract.current_crf_balance is None or not points:
        reasons = []
        if extract.current_crf_balance is None:
            reasons.append("no current CRF balance")
        if not points:
            reasons.append("no datable projected expenditures")
        return ReserveOutlook(
            building=building,
            unit=unit,
            start_balance=extract.current_crf_balance,
            degraded=True,
            degraded_reason="; ".join(reasons),
        )

    anchor = extract.balance_as_of_date or extract.report_date
    proj_start = anchor.year if anchor else min(p.year for p in points)
    horizon = max(p.year for p in points)
    if horizon <= proj_start:
        horizon = proj_start + _DEFAULT_HORIZON_YEARS

    assumptions = Assumptions(
        interest_rate=_rate_as_fraction(extract.interest_rate),
        base_annual_contribution=extract.recommended_annual_contribution,
        history_start_year=proj_start,
        projection_start_year=proj_start,
        horizon_end_year=horizon,
        sourced=True,
    )
    events = [
        TimelineEvent(
            year=float(p.year),
            row=i % 2,
            type="work",
            label=f"{p.label} {_short_amt(p.amount)}".strip(),
        )
        for i, p in enumerate(points)
    ]
    return ReserveOutlook(
        building=building,
        unit=unit,
        assumptions=assumptions,
        start_balance=extract.current_crf_balance,
        history=[],
        expenditures=points,
        planned_fee_changes=[],
        events=events,
    )
