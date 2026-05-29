"""Compare a StrataExtract against a hand-written JSON label.

Honest reporting: raw counts, denominators always visible, no synthetic
percentage. Hallucinations are counted ONLY when the label is complete
("complete": true); otherwise an extracted-but-unlabeled fact is unknown,
not a hallucination.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from yonder.extract.schema import StrataExtract


class ResultType(str, Enum):
    MATCH = "match"
    WRONG = "wrong-value"
    MISSED = "missed"
    UNLABELED_EXTRA = "unlabeled-extra"
    HALLUCINATION = "hallucination"


@dataclass
class FieldResult:
    field: str
    type: ResultType
    expected: str | None = None
    got: str | None = None
    low_confidence: bool = False


def _norm_purpose(purpose: str | None) -> str:
    return (purpose or "").strip().lower()


def _score_scalar(field: str, got, expected, results: list[FieldResult]) -> None:
    """expected is present in the label; decide match/wrong/missed."""
    if got is None:
        results.append(FieldResult(field, ResultType.MISSED, expected=str(expected)))
    elif str(got) == str(expected):
        results.append(FieldResult(field, ResultType.MATCH, expected=str(expected), got=str(got)))
    else:
        results.append(
            FieldResult(field, ResultType.WRONG, expected=str(expected), got=str(got))
        )


def _score_unit_entitlement(extract: StrataExtract, label: dict, results: list[FieldResult]) -> None:
    exp = label["unit_entitlement"]
    expected_ratio = f"{exp.get('numerator')}/{exp.get('denominator')}"
    ue = extract.unit_entitlement
    got_ratio = None if ue is None else f"{ue.numerator}/{ue.denominator}"
    _score_scalar("unit_entitlement", got_ratio, expected_ratio, results)


def _score_reserve_trend(extract: StrataExtract, label: dict, results: list[FieldResult]) -> None:
    expected = label["reserve_fund"].get("trend")
    rf = extract.reserve_fund
    got = None if rf is None or rf.trend is None else rf.trend.value
    _score_scalar("reserve_fund.trend", got, expected, results)


def _score_special_levies(extract: StrataExtract, label: dict, results: list[FieldResult]) -> None:
    expected_levies = label["special_levies"]
    got_by_purpose = {_norm_purpose(lv.purpose): lv for lv in extract.special_levies}
    matched_purposes = set()

    for exp in expected_levies:
        key = _norm_purpose(exp.get("purpose"))
        field = f"special_levies[{exp.get('purpose')}]"
        got = got_by_purpose.get(key)
        if got is None:
            results.append(
                FieldResult(field, ResultType.MISSED, expected=str(exp.get("purpose")))
            )
            continue
        matched_purposes.add(key)
        if exp.get("amount") is not None and got.amount != exp["amount"]:
            results.append(
                FieldResult(
                    field,
                    ResultType.WRONG,
                    expected=f"${exp['amount']}",
                    got=f"${got.amount}",
                )
            )
        else:
            results.append(FieldResult(field, ResultType.MATCH, expected=str(exp.get("purpose"))))

    # Extracted levies not in the label.
    complete = bool(label.get("complete", False))
    extra_type = ResultType.HALLUCINATION if complete else ResultType.UNLABELED_EXTRA
    for purpose_key, lv in got_by_purpose.items():
        if purpose_key not in matched_purposes:
            results.append(
                FieldResult(
                    f"special_levies[{lv.purpose}]",
                    extra_type,
                    got=str(lv.purpose),
                )
            )


def score_extract(extract: StrataExtract, label: dict) -> list[FieldResult]:
    """Return a flat list of per-field results. Only fields the label asserts
    are scored; nothing is invented."""
    results: list[FieldResult] = []
    if "unit_entitlement" in label:
        _score_unit_entitlement(extract, label, results)
    if "reserve_fund" in label and "trend" in label["reserve_fund"]:
        _score_reserve_trend(extract, label, results)
    if "special_levies" in label:
        _score_special_levies(extract, label, results)
    return results


def tally(results: list[FieldResult]) -> dict[ResultType, int]:
    counts = {t: 0 for t in ResultType}
    for r in results:
        counts[r.type] += 1
    return counts
