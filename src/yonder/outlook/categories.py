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

# Lowercased substring keywords, checked in SYSTEMS order.
_KEYWORDS: dict[str, tuple[str, ...]] = {
    ENVELOPE: (
        "roof", "wall", "window", "membrane", "sealant", "guardrail",
        "balcony", "door", "paint", "coating", "waterproof", "deck",
        "entrance", "slab", "panel", "eyebrow",
    ),
    MECHANICAL: (
        "hvac", "boiler", "hot water", "tank", "cooling", "heat exchanger",
        "pump", "mechanical", "ventilation",
    ),
    PLUMBING_FIRE: (
        "pipe", "sprinkler", "fire", "drainage", "sump", "sewer",
        "plumbing", "gas",
    ),
    ELECTRICAL_VERTICAL: (
        "elevator", "lift", "generator", "power", "lighting",
        "electrical", "distribution",
    ),
    AMENITIES_SITE: (
        "lobby", "hallway", "common", "playground", "mailbox", "landscap",
        "softscap", "hardscap", "garden", "site", "signage", "compactor",
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
