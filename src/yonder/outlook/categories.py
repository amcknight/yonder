"""Map a raw reserve-expenditure label to one of five building-system buckets.

The mapping is deliberately small and keyword-driven; it is the single source of
truth for label -> system. The reserve-chart preview mirrors this keyword table
in JS, so keep the two in sync (see docs/mockups/reserve-bubbles.html).

Buckets are checked in SYSTEMS order, so that order also resolves ties when a
label contains keywords from more than one bucket.
"""

from __future__ import annotations

ENVELOPE = "Envelope"
MECHANICAL = "Mechanical"
PLUMBING_FIRE = "Plumbing & Fire"
ELECTRICAL_VERTICAL = "Electrical & Vertical"
AMENITIES_SITE = "Amenities & Site"

# Priority order: earlier buckets win ties. AMENITIES_SITE is also the fallback.
SYSTEMS = [ENVELOPE, MECHANICAL, PLUMBING_FIRE, ELECTRICAL_VERTICAL, AMENITIES_SITE]

__all__ = [
    "ENVELOPE",
    "MECHANICAL",
    "PLUMBING_FIRE",
    "ELECTRICAL_VERTICAL",
    "AMENITIES_SITE",
    "SYSTEMS",
    "categorize",
]

# Lowercased substring keywords, checked in SYSTEMS order.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    ENVELOPE: (
        "roof", "wall", "window", "membrane", "sealant", "guardrail",
        "balcony",
        "doors",  # plural avoids "outdoor" false match; bare-singular "door" labels are rare
        "paint", "coating", "waterproof", "deck",
        "entrance", "slab",
        "metal panel",  # was bare "panel" — avoids mis-routing "Electrical Panel Replacement"
        "eyebrow",
    ),
    MECHANICAL: (
        "hvac", "boiler", "hot water", "tank", "cooling", "heat exchanger",
        "pump", "mechanical", "ventilation",
    ),
    PLUMBING_FIRE: (
        "pipe", "sprinkler", "fire", "drainage", "sump", "sewer",
        "plumbing",
        "gas",  # watch: non-pipe "gas" labels (e.g. gas station signage)
    ),
    ELECTRICAL_VERTICAL: (
        "elevator", "lift", "generator",
        "power",  # watch: "power washing" really belongs to Envelope
        "lighting",
        "electrical", "distribution",
    ),
    AMENITIES_SITE: (
        "lobby", "hallway", "common", "playground", "mailbox", "landscap",
        "softscap", "hardscap", "garden",
        "site",  # broad catch-all; watch "offsite"/"website"-style false matches
        "signage", "compactor",
        "garbage", "amenity", "feature", "pool", "gym", "fitness",
    ),
}


def categorize(label: str) -> str:
    """Return the system bucket for an expenditure label.

    Falls back to AMENITIES_SITE when no keyword matches.
    """
    text = label.lower()
    for system in SYSTEMS:
        if any(kw in text for kw in _KEYWORDS[system]):
            return system
    return AMENITIES_SITE
