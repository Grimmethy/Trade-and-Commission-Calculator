from app.sku_codes import (
    CONDITION_CODES,
    FACTION_CODES,
    IP_CODES,
    build_sku_prefix,
    condition_code,
    faction_code,
    ip_code,
)


def test_the_approved_example():
    # 40KTSC-001 = Warhammer 40,000 + Tyranids + Showcase
    assert build_sku_prefix("Warhammer 40,000", "Tyranids", "showcase") == "40KTSC"


def test_all_curated_ip_codes_are_1_to_3_chars():
    for name, code in IP_CODES.items():
        assert 1 <= len(code) <= 3, f"{name} -> {code!r}"


def test_all_curated_faction_codes_are_1_to_3_chars():
    for name, code in FACTION_CODES.items():
        assert 1 <= len(code) <= 3, f"{name} -> {code!r}"


def test_all_condition_codes_are_1_to_3_chars():
    for name, code in CONDITION_CODES.items():
        assert 1 <= len(code) <= 3, f"{name} -> {code!r}"


def test_condition_codes_cover_every_enum_value():
    assert set(CONDITION_CODES) == {"needs_repair", "assembled", "partial_paint", "showcase"}


def test_faction_codes_have_no_collisions_across_the_whole_table():
    # Codes only need to be unique within a game system in principle, but the
    # curated table happens to be globally unique too — worth locking in,
    # since a collision would silently merge two factions' SKU numbering.
    codes = list(FACTION_CODES.values())
    assert len(codes) == len(set(codes)), "duplicate faction code found"


def test_unmapped_faction_falls_back_to_derived_code():
    assert faction_code("Some Brand New Faction") == "SBN"


def test_unmapped_ip_falls_back_to_derived_code():
    assert ip_code("Some New Game") == "SNG"


def test_missing_ip_or_faction_uses_misc_fallback():
    assert ip_code(None) == "MSC"
    assert ip_code("") == "MSC"
    assert faction_code(None) == "MSC"


def test_unknown_condition_falls_back_to_xx():
    assert condition_code("not_a_real_condition") == "XX"


def test_build_sku_prefix_manual_dnd_entry():
    assert build_sku_prefix("D&D", "Custom", "assembled") == "DNDCUSAS"


def test_unmapped_single_word_faction_uses_first_letters():
    assert faction_code("Necrons") == "NEC"
