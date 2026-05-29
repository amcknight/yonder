import os
from pathlib import Path

import pytest

from yonder.extract.client import ClaudeClient
from yonder.extract.schema import StrataExtract
from yonder.extract.strata import extract_strata

SAMPLE = Path("fixtures/samples/sample-strata-package.pdf")

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="needs ANTHROPIC_API_KEY (live extraction)",
)


def test_sample_extracts_valid_structure():
    extract = extract_strata(SAMPLE.read_bytes(), client=ClaudeClient())
    assert isinstance(extract, StrataExtract)
    # Structural expectations — the synthetic doc clearly contains these.
    assert extract.unit_entitlement is not None
    assert extract.unit_entitlement.denominator == 2719
    assert len(extract.special_levies) >= 1
    assert len(extract.documents) >= 1
