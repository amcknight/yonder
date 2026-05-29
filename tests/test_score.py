from yonder.eval.score import ResultType, score_extract
from yonder.extract.schema import (
    ReserveFund,
    ReserveTrend,
    SpecialLevy,
    StrataExtract,
    UnitEntitlement,
)


def _result_for(results, field):
    return next(r for r in results if r.field == field)


def test_matching_ratio_scores_match():
    extract = StrataExtract(unit_entitlement=UnitEntitlement(numerator=18, denominator=2719))
    label = {"unit_entitlement": {"numerator": 18, "denominator": 2719}}
    results = score_extract(extract, label)
    assert _result_for(results, "unit_entitlement").type == ResultType.MATCH


def test_wrong_ratio_scores_wrong_value():
    extract = StrataExtract(unit_entitlement=UnitEntitlement(numerator=18, denominator=9999))
    label = {"unit_entitlement": {"numerator": 18, "denominator": 2719}}
    results = score_extract(extract, label)
    assert _result_for(results, "unit_entitlement").type == ResultType.WRONG


def test_missing_labeled_field_scores_missed():
    extract = StrataExtract()  # extracted nothing
    label = {"reserve_fund": {"trend": "declining"}}
    results = score_extract(extract, label)
    assert _result_for(results, "reserve_fund.trend").type == ResultType.MISSED


def test_trend_match():
    extract = StrataExtract(reserve_fund=ReserveFund(trend=ReserveTrend.DECLINING))
    label = {"reserve_fund": {"trend": "declining"}}
    results = score_extract(extract, label)
    assert _result_for(results, "reserve_fund.trend").type == ResultType.MATCH


def test_special_levies_matched_by_purpose():
    extract = StrataExtract(
        special_levies=[
            SpecialLevy(amount=4200.0, purpose="roof"),
            SpecialLevy(amount=850.0, purpose="elevator"),
        ]
    )
    label = {
        "special_levies": [
            {"amount": 4200.0, "purpose": "roof"},
            {"amount": 850.0, "purpose": "elevator"},
        ]
    }
    results = score_extract(extract, label)
    levy_results = [r for r in results if r.field.startswith("special_levies")]
    assert all(r.type == ResultType.MATCH for r in levy_results)
    assert len(levy_results) == 2


def test_missed_levy_is_flagged():
    extract = StrataExtract(special_levies=[SpecialLevy(amount=4200.0, purpose="roof")])
    label = {
        "special_levies": [
            {"amount": 4200.0, "purpose": "roof"},
            {"amount": 850.0, "purpose": "elevator"},
        ]
    }
    results = score_extract(extract, label)
    missed = [r for r in results if r.type == ResultType.MISSED]
    assert any("elevator" in (r.expected or "") for r in missed)


def test_extra_levy_partial_label_is_unlabeled_extra():
    extract = StrataExtract(
        special_levies=[
            SpecialLevy(amount=4200.0, purpose="roof"),
            SpecialLevy(amount=99.0, purpose="garden"),
        ]
    )
    label = {"complete": False, "special_levies": [{"amount": 4200.0, "purpose": "roof"}]}
    results = score_extract(extract, label)
    extras = [r for r in results if r.type == ResultType.UNLABELED_EXTRA]
    assert any("garden" in (r.got or "") for r in extras)


def test_extra_levy_complete_label_is_hallucination():
    extract = StrataExtract(
        special_levies=[
            SpecialLevy(amount=4200.0, purpose="roof"),
            SpecialLevy(amount=99.0, purpose="garden"),
        ]
    )
    label = {"complete": True, "special_levies": [{"amount": 4200.0, "purpose": "roof"}]}
    results = score_extract(extract, label)
    halluc = [r for r in results if r.type == ResultType.HALLUCINATION]
    assert any("garden" in (r.got or "") for r in halluc)
