from pathlib import Path

from yonder import cli
from yonder.outlook.model import ReserveOutlook
from yonder.outlook.schema import ProjectedExpenditure, ReserveExtract


def test_outlook_cli_writes_reserveoutlook(tmp_path, monkeypatch):
    canned = ReserveExtract(
        building_name="Test Tower",
        report_date="2022-05-01",
        current_crf_balance=350000,
        balance_as_of_date="2022-05-01",
        recommended_annual_contribution=90000,
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=180000, year=2028)],
    )
    # No API: stub the intelligence call and the client builder.
    monkeypatch.setattr(cli, "extract_reserve", lambda pdf_bytes, *, client: canned)
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = tmp_path / "outlook.json"

    rc = cli.main(["outlook", str(pdf), str(out)])
    assert rc == 0

    o = ReserveOutlook.model_validate_json(out.read_text(encoding="utf-8"))
    assert o.start_balance == 350000
    assert o.assumptions.sourced is True
    assert o.building.name == "Test Tower"


def test_outlook_cli_default_out_path_next_to_pdf(tmp_path, monkeypatch):
    canned = ReserveExtract(current_crf_balance=1, projected_expenditures=[
        ProjectedExpenditure(label="Roof", amount=1, year=2030)])
    monkeypatch.setattr(cli, "extract_reserve", lambda pdf_bytes, *, client: canned)
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "MyReport.pdf"
    pdf.write_bytes(b"%PDF fake")
    rc = cli.main(["outlook", str(pdf)])
    assert rc == 0
    assert (tmp_path / "MyReport.reserve_outlook.json").exists()


def test_outlook_cli_txt_source_uses_text_extractor(tmp_path, monkeypatch):
    canned = ReserveExtract(
        building_name="From Text",
        balance_as_of_date="2022-01-01",
        current_crf_balance=900000,
        recommended_annual_contribution=108000,
        projected_expenditures=[ProjectedExpenditure(label="Roof", amount=180000, year=2028)],
    )
    seen = {}

    def fake_from_text(text, *, client):
        seen["text"] = text
        return canned

    # A .txt source must route through the text extractor, never the PDF one.
    monkeypatch.setattr(cli, "extract_reserve_from_text", fake_from_text)
    monkeypatch.setattr(cli, "extract_reserve", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("PDF extractor must not be called for a .txt source")))
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    txt = tmp_path / "report.txt"
    txt.write_text("ROOF 2028 $180,000; CRF balance $900,000", encoding="utf-8")
    out = tmp_path / "o.json"

    rc = cli.main(["outlook", str(txt), str(out)])
    assert rc == 0
    assert seen["text"].startswith("ROOF 2028")
    o = ReserveOutlook.model_validate_json(out.read_text(encoding="utf-8"))
    assert o.start_balance == 900000
    assert o.building.name == "From Text"
