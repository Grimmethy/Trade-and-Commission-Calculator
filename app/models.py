from dataclasses import dataclass, field


@dataclass
class Item:
    id: int
    side: str
    name: str
    qty: int
    unit_price: float
    source: str
    catalog_item_id: int | None = None
    box_price: float | None = None
    models_per_box: int | None = None
    condition: str = "assembled"
    verified: bool = False
    verify_note: str | None = None

    @property
    def line_total(self) -> float:
        return self.qty * self.unit_price

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "side": self.side,
            "name": self.name,
            "qty": self.qty,
            "unit_price": self.unit_price,
            "line_total": self.line_total,
            "source": self.source,
            "catalog_item_id": self.catalog_item_id,
            "box_price": self.box_price,
            "models_per_box": self.models_per_box,
            "condition": self.condition,
            "verified": self.verified,
            "verify_note": self.verify_note,
        }


@dataclass
class Room:
    id: int
    code: str
    label_a: str
    label_b: str
    cash_a: float
    cash_b: float
    trade_venue: str = "direct"
    in_person_differential: float = 0.20
    online_differential: float = 0.40
    commission_side: str | None = None
    commission_type: str = "percentage"
    commission_rate: float = 0.40
    commission_base: float = 0
    commission_flat_amount: float = 0
    items: list[Item] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "label_a": self.label_a,
            "label_b": self.label_b,
            "cash_a": self.cash_a,
            "cash_b": self.cash_b,
            "trade_venue": self.trade_venue,
            "in_person_differential": self.in_person_differential,
            "online_differential": self.online_differential,
            "commission_side": self.commission_side,
            "commission_type": self.commission_type,
            "commission_rate": self.commission_rate,
            "commission_base": self.commission_base,
            "commission_flat_amount": self.commission_flat_amount,
        }


@dataclass
class Commission:
    id: int
    code: str
    painter_name: str
    status: str
    commission_rate: float
    cash_amount: float
    items: list[Item] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "painter_name": self.painter_name,
            "status": self.status,
            "commission_rate": self.commission_rate,
            "cash_amount": self.cash_amount,
        }


@dataclass
class CatalogItem:
    id: int
    ip: str
    faction: str
    item_name: str
    box_price: float
    website_link: str | None
    image_url: str | None
    models_per_box: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ip": self.ip,
            "faction": self.faction,
            "item_name": self.item_name,
            "box_price": self.box_price,
            "website_link": self.website_link,
            "image_url": self.image_url,
            "models_per_box": self.models_per_box,
        }


@dataclass
class InventoryPhoto:
    id: int
    inventory_item_id: int
    filename: str
    original_filename: str | None
    content_type: str | None
    is_primary: bool
    sort_order: int
    uploaded_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inventory_item_id": self.inventory_item_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "is_primary": self.is_primary,
            "sort_order": self.sort_order,
            "uploaded_at": self.uploaded_at,
        }


@dataclass
class InventoryItem:
    id: int
    sku: str
    name: str
    ip: str | None = None
    faction: str | None = None
    source: str = "manual"
    catalog_item_id: int | None = None
    box_price: float | None = None
    models_per_box: int | None = None
    qty: int = 1
    condition: str = "assembled"
    third_party_price: float | None = None
    sp_min: float | None = None
    sp_max: float | None = None
    sell_price: float | None = None
    date_sold: str | None = None
    status: str = "in_stock"
    notes: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    photos: list[InventoryPhoto] = field(default_factory=list)

    @property
    def primary_photo(self) -> InventoryPhoto | None:
        for photo in self.photos:
            if photo.is_primary:
                return photo
        return None

    @property
    def label_price(self) -> float:
        """Asking price shown on the printed tag: sp_max, falling back down the
        chain to whatever's actually set, unless the item has already sold, in
        which case the real sell price is what belongs on a reprinted tag."""
        if self.status == "sold" and self.sell_price is not None:
            return self.sell_price
        return self.sp_max or self.sp_min or self.third_party_price or 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "ip": self.ip,
            "faction": self.faction,
            "source": self.source,
            "catalog_item_id": self.catalog_item_id,
            "box_price": self.box_price,
            "models_per_box": self.models_per_box,
            "qty": self.qty,
            "condition": self.condition,
            "third_party_price": self.third_party_price,
            "sp_min": self.sp_min,
            "sp_max": self.sp_max,
            "sell_price": self.sell_price,
            "date_sold": self.date_sold,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "photos": [p.to_dict() for p in self.photos],
        }
