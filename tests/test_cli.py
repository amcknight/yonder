from yonder.cli import find_labeled_pdfs, render_report
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


def test_find_labeled_pdfs_recurses_and_resolves_labels(tmp_path):
    # nested PDF with a sibling <stem>.expected.json label
    sub = tmp_path / "minutes" / "2024"
    sub.mkdir(parents=True)
    (sub / "agm.pdf").write_bytes(b"%PDF-1.4")
    (sub / "agm.expected.json").write_text("{}")
    # nested PDF covered by a folder-level expected.json
    other = tmp_path / "financials"
    other.mkdir()
    (other / "fs.pdf").write_bytes(b"%PDF-1.4")
    (other / "expected.json").write_text("{}")
    # nested PDF with no label
    (sub / "scm.pdf").write_bytes(b"%PDF-1.4")

    labeled, unlabeled = find_labeled_pdfs(tmp_path)

    labeled_names = {pdf.name for pdf, _ in labeled}
    assert labeled_names == {"agm.pdf", "fs.pdf"}
    assert [p.name for p in unlabeled] == ["scm.pdf"]
    # the sibling label wins for agm.pdf
    agm_label = next(label for pdf, label in labeled if pdf.name == "agm.pdf")
    assert agm_label.name == "agm.expected.json"
