from app.labels import build_label_zpl, esc, format_price, make_zpl, pick_font_size
from app.models import InventoryItem


def test_pick_font_size_boundaries():
    assert pick_font_size("a" * 14) == (120, 72)
    assert pick_font_size("a" * 15) == (96, 56)
    assert pick_font_size("a" * 20) == (96, 56)
    assert pick_font_size("a" * 21) == (64, 40)
    assert pick_font_size("a" * 32) == (64, 40)
    assert pick_font_size("a" * 33) == (48, 28)


def test_format_price_valid_number():
    assert format_price(43.5) == "$43.50"
    assert format_price("43.5") == "$43.50"


def test_format_price_invalid_falls_back_to_tbd():
    assert format_price(None) == "TBD"
    assert format_price("") == "TBD"
    assert format_price("   ") == "TBD"


def test_format_price_non_numeric_string_passes_through():
    assert format_price("Ask") == "Ask"


def test_esc_strips_zpl_delimiters():
    assert esc("^FDweird~name^") == "FDweirdname"


def test_make_zpl_contains_expected_fields():
    zpl = make_zpl(sku="gwsgl001", name="Vengorian Lord", qty=2, price=125.0, notes="chipped base", image_path=None)
    assert "SKU: gwsgl001" in zpl
    assert "FDVengorian Lord" in zpl
    assert "Qty: 2" in zpl
    assert "Price: $125.00" in zpl
    assert "Notes: chipped base" in zpl
    assert "No image on file" in zpl


def test_make_zpl_blank_notes_becomes_na():
    zpl = make_zpl(sku="x001", name="Test", qty=1, price=10, notes="", image_path=None)
    assert "Notes: N/A" in zpl


def _item(**overrides) -> InventoryItem:
    defaults = dict(id=1, sku="gwsgl001", name="Vengorian Lord")
    defaults.update(overrides)
    return InventoryItem(**defaults)


def test_build_label_zpl_price_fallback_chain():
    # No third_party_price/sp_min/sp_max set at all -> falls all the way to 0.0
    assert _item().label_price == 0.0

    assert _item(third_party_price=50.0).label_price == 50.0
    assert _item(third_party_price=50.0, sp_min=40.0).label_price == 40.0
    assert _item(third_party_price=50.0, sp_min=40.0, sp_max=75.0).label_price == 75.0


def test_build_label_zpl_uses_sell_price_once_sold():
    item = _item(sp_max=75.0, status="sold", sell_price=60.0)
    assert item.label_price == 60.0
    zpl = build_label_zpl(item, photo_path=None)
    assert "Price: $60.00" in zpl


def test_build_label_zpl_price_override_does_not_touch_stored_data():
    item = _item(sp_max=75.0)
    zpl = build_label_zpl(item, photo_path=None, price_override=99.99)
    assert "Price: $99.99" in zpl
    assert item.sp_max == 75.0  # override never mutates the item
