from yonder.cli import render_report
from yonder.eval.score import FieldResult, ResultType


def test_render_report_shows_denominators_and_counts():
    results = [
        FieldResult("unit_entitlement", ResultType.MATCH, expected="18/2719", got="18/2719"),
        FieldResult("special_levies[elevator]", ResultType.MISSED, expected="elevator"),
        FieldResult("special_levies[roof]", ResultType.MATCH, expected="roof"),
    ]
    out = render_report("sample-strata-package", results, complete=True)
    assert "sample-strata-package" in out
    assert "label: complete" in out
    assert "match: 2" in out
    assert "missed: 1" in out
    # No synthetic percentage anywhere.
    assert "%" not in out


def test_render_report_marks_partial_label():
    out = render_report("real-doc", [], complete=False)
    assert "label: partial" in out
