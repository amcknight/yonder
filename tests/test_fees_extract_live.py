import os
from pathlib import Path

import pytest

from yonder.extract.client import ClaudeClient
from yonder.fees.extract import extract_fees
from yonder.fees.schema import FeeExtract

SAMPLE = Path("fixtures/samples/sample-strata-package.pdf")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="needs ANTHROPIC_API_KEY (live extraction)",
)


def test_sample_fees_extract_has_budget_and_schedule():
    e = extract_fees(SAMPLE.read_bytes(), client=ClaudeClient())
    assert isinstance(e, FeeExtract)
    # The synthetic budget page clearly contains these.
    assert len(e.operating_budget) >= 5
    assert all(li.parent_category for li in e.operating_budget)
    assert any(li.parent_category == "Reserve contribution" for li in e.operating_budget)
    # The synthetic fee schedule lists lot 1802.
    assert any(lot.lot_id == "1802" for lot in e.fee_schedule)
