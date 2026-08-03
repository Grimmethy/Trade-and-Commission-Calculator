"""Curated abbreviation codes for SGC's strict SKU scheme, approved 2026-08-03.

Format: <game code><faction code><condition code>-<entry number>
e.g. 40KTSC-001 = Warhammer 40,000 + Tyranids + Showcase, entry 1.

Codes are 1-3 characters each, individually chosen (not fixed-width) — the
SKU is a generated, human-facing label, not something parsed back into
structured data (ip/faction/condition already live as real columns on
inventory_items), so variable-width concatenation is fine.

Catalog-sourced items always have an ip/faction from this exact table (the
same catalog data these codes were derived from). Manual entries can name
anything, so unmapped names fall back to a derived code rather than failing.
"""

IP_CODES = {
    "Warhammer 40,000": "40K",
    "Age of Sigmar": "AOS",
    "Horus Heresy": "HH",
    "D&D": "DND",
}

FACTION_CODES = {
    # Warhammer 40,000
    "Tyranids": "T",
    "Space Marines": "SM",
    "Chaos Space Marines": "CSM",
    "Aeldari": "AE",
    "Astra Militarum": "AM",
    # Age of Sigmar
    "Beasts of Chaos": "BOC",
    "Blades of Khorne": "BOK",
    "Cities of Sigmar": "COS",
    "Daughters of Khaine": "DOK",
    "Disciples of Tzeentch": "DOT",
    "Flesh-eater Courts": "FEC",
    "Fyreslayers": "FYR",
    "Gloomspite Gitz": "GG",
    "Hedonites of Slaanesh": "HOS",
    "Idoneth Deepkin": "IDK",
    "Kharadron Overlords": "KO",
    "Lumineth Realm-lords": "LRL",
    "Maggotkin of Nurgle": "MON",
    "Nighthaunt": "NH",
    "Ogor Mawtribes": "OM",
    "Orruk Warclans": "OW",
    "Ossiarch Bonereapers": "OB",
    "Seraphon": "SER",
    "Skaven": "SKV",
    "Slaves to Darkness": "STD",
    "Sons of Behemat": "SOB",
    "Soulblight Gravelords": "SBG",
    "Stormcast Eternals": "SCE",
    "Sylvaneth": "SYL",
    # Horus Heresy
    "The Horus Heresy – Vehicles": "VEH",
}

CONDITION_CODES = {
    "assembled": "AS",
    "needs_repair": "NR",
    "partial_paint": "PP",
    "showcase": "SC",
}

_FALLBACK_CODE = "MSC"  # used when ip/faction is missing entirely


def _derive_fallback_code(name: str, max_len: int = 3) -> str:
    """For freeform manual-entry names not in the curated tables — initials
    of up to max_len words, matching the style most curated codes already
    follow (e.g. "Beasts of Chaos" -> BOC). Falls back to the first max_len
    letters of the name itself for a single-word name. Not guaranteed to
    avoid colliding with a curated code; good enough for the long-tail case
    this exists for — the curated table is what "strict" actually relies on."""
    words = [w for w in name.split() if any(ch.isalpha() for ch in w)]
    if len(words) >= 2:
        initials = []
        for w in words[:max_len]:
            for ch in w:
                if ch.isalpha():
                    initials.append(ch.upper())
                    break
        if len(initials) >= 2:
            return "".join(initials)
    letters = "".join(ch for ch in name.upper() if ch.isalpha())
    return letters[:max_len] or "X"


def ip_code(ip: str | None) -> str:
    if not ip:
        return _FALLBACK_CODE
    return IP_CODES.get(ip) or _derive_fallback_code(ip)


def faction_code(faction: str | None) -> str:
    if not faction:
        return _FALLBACK_CODE
    return FACTION_CODES.get(faction) or _derive_fallback_code(faction)


def condition_code(condition: str) -> str:
    return CONDITION_CODES.get(condition, "XX")


def build_sku_prefix(ip: str | None, faction: str | None, condition: str) -> str:
    return f"{ip_code(ip)}{faction_code(faction)}{condition_code(condition)}"
