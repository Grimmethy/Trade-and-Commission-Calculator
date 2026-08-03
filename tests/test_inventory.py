import aiosqlite
import pytest
import pytest_asyncio

from app import db as db_module
from app import inventory


@pytest_asyncio.fixture
async def test_db():
    """In-memory DB, schema only — no catalog seed needed for these tests."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.executescript(db_module.SCHEMA)
    await conn.commit()
    db_module._db = conn
    yield conn
    await conn.close()
    db_module._db = None


@pytest.mark.asyncio
async def test_generate_sku_starts_at_one(test_db):
    assert await inventory.generate_sku("gwsgl") == "gwsgl-001"


@pytest.mark.asyncio
async def test_generate_sku_increments_past_existing(test_db):
    await inventory.create_item(sku="gwsgl-001", name="A")
    await inventory.create_item(sku="gwsgl-002", name="B")
    assert await inventory.generate_sku("gwsgl") == "gwsgl-003"


@pytest.mark.asyncio
async def test_generate_sku_self_heals_after_deletion(test_db):
    id1 = await inventory.create_item(sku="gwsgl-001", name="A")
    await inventory.create_item(sku="gwsgl-002", name="B")
    await inventory.remove_item(id1)
    # gwsgl-001 is free again — no separate counter table to drift out of sync
    assert await inventory.generate_sku("gwsgl") == "gwsgl-001"


@pytest.mark.asyncio
async def test_set_pricing_derives_sp_range(test_db):
    item_id = await inventory.create_item(sku="gwsgl001", name="A")
    await inventory.set_pricing(item_id, 100.0)
    item = await inventory.get_item(item_id)
    assert item.third_party_price == 100.0
    assert item.sp_min == 80.0
    assert item.sp_max == 150.0


@pytest.mark.asyncio
async def test_first_photo_uploaded_is_automatically_primary(test_db):
    item_id = await inventory.create_item(sku="gwsgl001", name="A")
    photo_id = await inventory.add_photo(item_id, "gwsgl001_1.jpg", "orig.jpg", "image/jpeg")
    item = await inventory.get_item(item_id)
    assert item.primary_photo.id == photo_id


@pytest.mark.asyncio
async def test_second_photo_is_not_primary_until_explicitly_set(test_db):
    item_id = await inventory.create_item(sku="gwsgl001", name="A")
    first_id = await inventory.add_photo(item_id, "gwsgl001_1.jpg", "a.jpg", "image/jpeg")
    second_id = await inventory.add_photo(item_id, "gwsgl001_2.jpg", "b.jpg", "image/jpeg")

    item = await inventory.get_item(item_id)
    assert item.primary_photo.id == first_id

    await inventory.set_primary_photo(item_id, second_id)
    item = await inventory.get_item(item_id)
    assert item.primary_photo.id == second_id
    # exactly one primary — the DB's partial unique index would raise on a
    # violation, so getting here at all is part of the assertion
    primaries = [p for p in item.photos if p.is_primary]
    assert len(primaries) == 1


@pytest.mark.asyncio
async def test_deleting_primary_photo_promotes_next_one(test_db):
    item_id = await inventory.create_item(sku="gwsgl001", name="A")
    first_id = await inventory.add_photo(item_id, "gwsgl001_1.jpg", "a.jpg", "image/jpeg")
    second_id = await inventory.add_photo(item_id, "gwsgl001_2.jpg", "b.jpg", "image/jpeg")

    await inventory.remove_photo(first_id)
    item = await inventory.get_item(item_id)
    assert item.primary_photo.id == second_id


@pytest.mark.asyncio
async def test_deleting_only_photo_leaves_no_primary(test_db):
    item_id = await inventory.create_item(sku="gwsgl001", name="A")
    photo_id = await inventory.add_photo(item_id, "gwsgl001_1.jpg", "a.jpg", "image/jpeg")
    await inventory.remove_photo(photo_id)
    item = await inventory.get_item(item_id)
    assert item.primary_photo is None


@pytest.mark.asyncio
async def test_mark_sold_sets_status_and_sell_price(test_db):
    item_id = await inventory.create_item(sku="gwsgl001", name="A")
    await inventory.mark_sold(item_id, 60.0, "2026-08-02")
    item = await inventory.get_item(item_id)
    assert item.status == "sold"
    assert item.sell_price == 60.0
    assert item.date_sold == "2026-08-02"
