from app.exports import (
    EBAY_STATIC_COLUMNS,
    SQUARE_STATIC_COLUMNS,
    build_ebay_rows,
    build_square_rows,
)
from app.models import InventoryItem


def _item(**overrides) -> InventoryItem:
    defaults = dict(
        id=1,
        sku="gwsgl001",
        name="Vengorian Lord",
        ip="Age of Sigmar",
        faction="Soulblight Gravelords",
        qty=1,
        condition="showcase",
        sp_max=125.0,
        notes="painted, minor chip on base",
    )
    defaults.update(overrides)
    return InventoryItem(**defaults)


def test_build_square_rows_static_columns():
    rows = build_square_rows([_item()])
    assert len(rows) == 1
    row = rows[0]
    assert set(row.keys()) == set(SQUARE_STATIC_COLUMNS)
    assert row["Item Name"] == "Vengorian Lord"
    assert row["SKU"] == "gwsgl001"
    assert row["Category"] == "Age of Sigmar"
    assert row["Reporting Category"] == "Soulblight Gravelords"
    assert row["Price"] == "125.00"
    assert row["New Quantity"] == "1"
    assert row["Enabled"] == "Y"


def test_build_ebay_rows_static_columns():
    rows = build_ebay_rows([_item()])
    row = rows[0]
    assert set(row.keys()) == set(EBAY_STATIC_COLUMNS)
    assert row["Custom label (SKU)"] == "gwsgl001"
    assert row["Title"] == "Vengorian Lord"
    assert row["StartPrice"] == "125.00"
    assert row["Format"] == "FixedPrice"
    assert row["Duration"] == "GTC"


def test_build_ebay_rows_picurl_always_blank():
    # Photos can't be attached via CSV for either platform — this must never
    # silently start filling in a local path that eBay can't fetch.
    rows = build_ebay_rows([_item()])
    assert rows[0]["PicURL"] == ""


def test_build_ebay_rows_condition_maps_to_used_by_default():
    for condition in ("needs_repair", "assembled", "partial_paint", "showcase"):
        row = build_ebay_rows([_item(condition=condition)])[0]
        assert row["ConditionID"] == "3000"


def test_build_ebay_rows_category_blank_when_unmapped():
    row = build_ebay_rows([_item(ip="Unmapped Game", faction="Unmapped Faction")])[0]
    assert row["Category"] == ""


def test_build_rows_title_truncated_to_ebay_limit():
    row = build_ebay_rows([_item(name="X" * 100)])[0]
    assert len(row["Title"]) == 80


def test_build_rows_with_custom_template_headers():
    headers = ["SKU", "Item Name", "Some Unknown Column"]
    row = build_square_rows([_item()], headers=headers)[0]
    assert set(row.keys()) == set(headers)
    assert row["SKU"] == "gwsgl001"
    assert row["Some Unknown Column"] == ""
