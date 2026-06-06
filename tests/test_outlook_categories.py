from yonder.outlook.categories import (
    SYSTEMS,
    categorize,
    ENVELOPE,
    MECHANICAL,
    PLUMBING_FIRE,
    ELECTRICAL_VERTICAL,
    AMENITIES_SITE,
)


def test_systems_is_the_five_buckets_in_priority_order():
    assert SYSTEMS == [
        ENVELOPE,
        MECHANICAL,
        PLUMBING_FIRE,
        ELECTRICAL_VERTICAL,
        AMENITIES_SITE,
    ]


def test_obvious_labels_map_to_expected_systems():
    assert categorize("Low-Slope Roof") == ENVELOPE
    assert categorize("Hot Water Tanks") == MECHANICAL
    assert categorize("Domestic Water Pipes") == PLUMBING_FIRE
    assert categorize("Elevator Modernization") == ELECTRICAL_VERTICAL
    assert categorize("Lobby") == AMENITIES_SITE


def test_unmatched_label_falls_back_to_amenities_site():
    assert categorize("Something Totally Unknown") == AMENITIES_SITE


def test_match_is_case_insensitive():
    assert categorize("low-slope ROOF") == ENVELOPE


import pytest

# (label, expected system) for the real Spectrum 4 depreciation-report items.
SPECTRUM4_CASES = [
    ("Hot Water Tanks", MECHANICAL),
    ("Expansion Tanks", MECHANICAL),
    ("Reheat Tanks", MECHANICAL),
    ("HVAC Parkade", MECHANICAL),
    ("Balcony Membrane", ENVELOPE),
    ("Conc Eyebrow Membrane", ENVELOPE),
    ("Sealant", ENVELOPE),
    ("Paint Coating", ENVELOPE),
    ("Heat Exchanger", MECHANICAL),
    ("Lobby", AMENITIES_SITE),
    ("Hallways/Common", AMENITIES_SITE),
    ("HVAC Building", MECHANICAL),
    ("Misc Mechanical", MECHANICAL),
    ("Water Pumps", MECHANICAL),
    ("Garbage Compactor", AMENITIES_SITE),
    ("Playground", AMENITIES_SITE),
    ("Sliding Doors", ENVELOPE),
    ("Balcony Swing Doors", ENVELOPE),
    ("Front Entrance", ENVELOPE),
    ("Low-Slope Roof", ENVELOPE),
    ("Below-Grade Membrane", ENVELOPE),
    ("Garden Waterproofing", ENVELOPE),
    ("Balcony Guardrails", ENVELOPE),
    ("Roof Decks", ENVELOPE),
    ("Elevator Modernization", ELECTRICAL_VERTICAL),
    ("Elevator Cab", ELECTRICAL_VERTICAL),
    ("Domestic Water Pipes", PLUMBING_FIRE),
    ("Sprinkler/Fire", PLUMBING_FIRE),
    ("Cooling Tower", MECHANICAL),
    ("Service Distribution", ELECTRICAL_VERTICAL),
    ("Mailboxes", AMENITIES_SITE),
    ("Outdoor Lighting", ELECTRICAL_VERTICAL),
    ("Site Handrails", AMENITIES_SITE),
    ("Water Feature", AMENITIES_SITE),
    ("Emergency Generator", ELECTRICAL_VERTICAL),
    ("Entry Doors", ENVELOPE),
    ("Service Doors", ENVELOPE),
    ("Power Distribution", ELECTRICAL_VERTICAL),
    ("Softscaping", AMENITIES_SITE),
    ("Hardscaping", AMENITIES_SITE),
    ("Drainage", PLUMBING_FIRE),
    ("Conc Balcony Slabs", ENVELOPE),
    ("Ext Walls Concrete", ENVELOPE),
    ("Ext Walls Metal Panel", ENVELOPE),
    ("Window-wall", ENVELOPE),
    ("Interior Doors", ENVELOPE),
    ("Gas Pipes", PLUMBING_FIRE),
]


@pytest.mark.parametrize("label,expected", SPECTRUM4_CASES)
def test_spectrum4_labels_classify_deterministically(label, expected):
    assert categorize(label) == expected
