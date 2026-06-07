import json
from pathlib import Path

from yonder import cli
from yonder.fees.model import FeeBreakdown
from yonder.fees.sample import wexford_fee_sample
from yonder.fees.schema import BudgetLineItem, FeeExtract, LotFee


def _canned_extract() -> FeeExtract:
    return FeeExtract(
        building_name="Test Tower",
        fiscal_year=2024,
        operating_budget=[
            BudgetLineItem(label="Insurance", parent_category="Insurance", annual_amount=182000),
            BudgetLineItem(label="Transfer to CRF", parent_category="Reserve contribution",
                           annual_amount=139000),
        ],
        fee_schedule=[LotFee(lot_id="1802", operating_monthly=521, crf_monthly=78)],
    )


def test_fees_cli_writes_feebreakdown(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "extract_fees", lambda pdf_bytes, *, client: _canned_extract())
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "agm.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    out = tmp_path / "fb.json"

    rc = cli.main(["fees", str(pdf), "--lot", "1802", str(out)])
    assert rc == 0

    fb = FeeBreakdown.model_validate_json(out.read_text(encoding="utf-8"))
    assert fb.building.name == "Test Tower"
    assert fb.unit.lot_id == "1802"
    assert fb.reserve.personal_monthly == 78


def test_fees_cli_default_out_path_next_to_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "extract_fees", lambda pdf_bytes, *, client: _canned_extract())
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    pdf = tmp_path / "MyAgm.pdf"
    pdf.write_bytes(b"%PDF fake")
    rc = cli.main(["fees", str(pdf)])
    assert rc == 0
    assert (tmp_path / "MyAgm.fee_breakdown.json").exists()


def test_fees_cli_txt_source_uses_text_extractor(tmp_path, monkeypatch):
    seen = {}

    def fake_from_text(text, *, client):
        seen["text"] = text
        return _canned_extract()

    monkeypatch.setattr(cli, "extract_fees_from_text", fake_from_text)
    monkeypatch.setattr(cli, "extract_fees", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("PDF extractor must not be called for a .txt source")))
    monkeypatch.setattr(cli, "_build_client", lambda: object())

    txt = tmp_path / "budget.txt"
    txt.write_text("INSURANCE 182000; CRF 139000", encoding="utf-8")
    out = tmp_path / "o.json"

    rc = cli.main(["fees", str(txt), "--lot", "1802", str(out)])
    assert rc == 0
    assert seen["text"].startswith("INSURANCE")


def test_fees_sample_cli_writes_valid_json(tmp_path):
    out = tmp_path / "sample.json"
    rc = cli.main(["fees-sample", str(out)])
    assert rc == 0
    loaded = FeeBreakdown.model_validate_json(out.read_text(encoding="utf-8"))
    assert loaded == wexford_fee_sample()
