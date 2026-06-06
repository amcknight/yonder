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
