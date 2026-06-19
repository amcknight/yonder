import datetime

import pytest
from pydantic import ValidationError

from yonder.extract.schema import (
    DocType,
    Meeting,
    ReserveTrend,
    SpecialLevy,
    StrataExtract,
    UnitEntitlement,
)


def test_empty_extract_is_valid():
    """Real docs are partial; an all-empty extract must validate."""
    extract = StrataExtract()
    assert extract.documents == []
    assert extract.special_levies == []
    assert extract.unit_entitlement is None


def test_unit_entitlement_from_ratio_string():
    ue = UnitEntitlement.from_ratio("18/2719")
    assert ue.numerator == 18
    assert ue.denominator == 2719


def test_unit_entitlement_from_ratio_tolerates_spaces():
    ue = UnitEntitlement.from_ratio("  18 / 2719 ")
    assert (ue.numerator, ue.denominator) == (18, 2719)


def test_unit_entitlement_from_ratio_rejects_garbage():
    with pytest.raises(ValueError):
        UnitEntitlement.from_ratio("not-a-ratio")


def test_special_levy_parses_iso_date():
    levy = SpecialLevy(amount=4200.0, date_approved="2023-11-15", purpose="roof")
    assert levy.date_approved == datetime.date(2023, 11, 15)


def test_doctype_defaults_to_other():
    extract = StrataExtract.model_validate({"documents": [{"issue_date": "2024-03-12"}]})
    assert extract.documents[0].type == DocType.OTHER


def test_reserve_trend_defaults_unknown():
    extract = StrataExtract.model_validate({"reserve_fund": {"balance": 100000.0}})
    assert extract.reserve_fund.trend == ReserveTrend.UNKNOWN


def test_unknown_doctype_rejected_so_model_must_use_other():
    with pytest.raises(ValidationError):
        StrataExtract.model_validate({"documents": [{"type": "tax_return"}]})


def test_meeting_type_accepts_agm_sgm_or_null():
    assert Meeting(type="AGM").type == "AGM"
    assert Meeting(type="SGM").type == "SGM"
    assert Meeting().type is None


def test_meeting_type_rejects_other_values():
    with pytest.raises(ValidationError):
        Meeting(type="EGM")
