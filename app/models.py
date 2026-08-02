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
