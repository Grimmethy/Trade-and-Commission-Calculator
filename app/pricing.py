from dataclasses import dataclass

from app.models import Item, Room

CONDITION_MULTIPLIERS = {
    "needs_repair": 0.80,
    "assembled": 1.00,
    "partial_paint": 1.00,
    "showcase": 1.40,
}

CONDITION_LABELS = {
    "needs_repair": "Needs Repair",
    "assembled": "Assembled",
    "partial_paint": "Partial Paint",
    "showcase": "Showcase",
}

DEFAULT_CONDITION = "assembled"

SP_MIN_MULTIPLIER = 0.8
SP_MAX_MULTIPLIER = 1.5


def compute_sp_range(third_party_price: float) -> tuple[float, float]:
    """SGC's standard asking-price range from a market/comp price: floor at 80%,
    ceiling at 150%. Written once alongside third_party_price rather than
    recomputed on every read, so a stored sp_min/sp_max always reflects the
    multipliers in effect when it was priced."""
    return (
        round(third_party_price * SP_MIN_MULTIPLIER, 2),
        round(third_party_price * SP_MAX_MULTIPLIER, 2),
    )


def apply_condition(base_price: float, condition: str) -> float:
    """Scales a price by a condition's multiplier — used when an item is first
    added (base_price is the derived/entered price, condition-free)."""
    return round(base_price * CONDITION_MULTIPLIERS[condition], 2)


def rebaseline_condition(current_price: float, old_condition: str, new_condition: str) -> float:
    """Recomputes a price when an existing item's condition changes — divides out
    the old multiplier to recover the true base price, then applies the new one.
    Without this, switching Needs Repair -> Showcase would apply 140% of the
    already-20%-discounted price instead of 140% of the true value."""
    old_multiplier = CONDITION_MULTIPLIERS[old_condition]
    base_price = current_price / old_multiplier if old_multiplier else current_price
    return round(base_price * CONDITION_MULTIPLIERS[new_condition], 2)

VENUE_LABELS = {
    "direct": "Direct trade",
    "in_person": "In-person via store",
    "online": "Online via store",
}

DEFAULT_IN_PERSON_DIFFERENTIAL = 0.20
DEFAULT_ONLINE_DIFFERENTIAL = 0.40


def venue_multiplier(venue: str, in_person_differential: float, online_differential: float) -> float:
    """The store's cut for a given trade venue, as a multiplier applied to item
    value (1.0 = no discount). A direct peer trade has no differential."""
    if venue == "in_person":
        return 1 - in_person_differential
    if venue == "online":
        return 1 - online_differential
    return 1.0


DEFAULT_COMMISSION_RATE = 0.40


def compute_commission_amount(
    commission_type: str, rate: float, base: float, flat_amount: float
) -> float:
    """A painting/service commission owed to whichever side commission_side names —
    either a percentage of the MSRP of the models being painted, or a flat rate."""
    if commission_type == "flat":
        return round(flat_amount, 2)
    return round(rate * base, 2)


def derive_per_model_price(box_price: float, models_per_box: int) -> float:
    if models_per_box <= 0:
        raise ValueError("models_per_box must be positive")
    return round(box_price / models_per_box, 2)


def side_total(items: list[Item], side: str) -> float:
    return round(sum(i.line_total for i in items if i.side == side), 2)


@dataclass
class BalanceResult:
    total_a: float
    total_b: float
    diff: float  # total_a - total_b, positive means A's items are worth more
    suggested_topup_side: str | None  # 'A', 'B', or None if balanced
    suggested_topup_amount: float


def compute_balance(
    total_a: float, total_b: float, cash_a: float = 0, cash_b: float = 0
) -> BalanceResult:
    net = (total_a) - (total_b) + (cash_a) - (cash_b)
    diff = round(total_a - total_b, 2)

    if abs(net) < 0.005:
        return BalanceResult(total_a, total_b, diff, None, 0.0)

    # net > 0 means side A's (items + cash) outweighs side B's — B should add cash to balance.
    if net > 0:
        return BalanceResult(total_a, total_b, diff, "B", round(net, 2))
    return BalanceResult(total_a, total_b, diff, "A", round(-net, 2))


@dataclass
class TotalsResult:
    total_a: float
    total_b: float
    venue_multiplier: float
    commission_amount: float
    effective_side_a: float
    effective_side_b: float
    diff: float
    suggested_topup_side: str | None
    suggested_topup_amount: float


def compute_totals(room: Room) -> TotalsResult:
    """Everything a trade room needs to display: raw item totals, the venue
    differential applied, any commission folded into whichever side it's owed
    to, and the resulting suggested cash top-up. The single place this math
    happens — the WebSocket handler just shapes this into a payload."""
    total_a = side_total(room.items, "A")
    total_b = side_total(room.items, "B")

    multiplier = venue_multiplier(room.trade_venue, room.in_person_differential, room.online_differential)
    effective_a = round(total_a * multiplier, 2)
    effective_b = round(total_b * multiplier, 2)

    commission_amount = 0.0
    if room.commission_side:
        commission_amount = compute_commission_amount(
            room.commission_type, room.commission_rate, room.commission_base, room.commission_flat_amount
        )
        # Commission is value owed TO commission_side — folding it into that
        # side's effective total means the other side has to bring that much
        # more (cash or items) to balance, exactly like an extra item on the
        # commissioned side's pile.
        if room.commission_side == "A":
            effective_a = round(effective_a + commission_amount, 2)
        else:
            effective_b = round(effective_b + commission_amount, 2)

    balance = compute_balance(effective_a, effective_b, room.cash_a, room.cash_b)

    return TotalsResult(
        total_a=total_a,
        total_b=total_b,
        venue_multiplier=multiplier,
        commission_amount=commission_amount,
        effective_side_a=effective_a,
        effective_side_b=effective_b,
        diff=balance.diff,
        suggested_topup_side=balance.suggested_topup_side,
        suggested_topup_amount=balance.suggested_topup_amount,
    )
