from app.pricing import (
    apply_condition,
    compute_balance,
    compute_totals,
    derive_per_model_price,
    rebaseline_condition,
    side_total,
)
from app.models import Item, Room


def _room(items=None, **overrides) -> Room:
    defaults = dict(id=1, code="test", label_a="Side A", label_b="Side B", cash_a=0, cash_b=0)
    defaults.update(overrides)
    return Room(items=items or [], **defaults)


def test_derive_per_model_price():
    assert derive_per_model_price(65.0, 5) == 13.0


def test_side_total():
    items = [
        Item(id=1, side="A", name="War Walker", qty=2, unit_price=42.5, source="catalog"),
        Item(id=2, side="A", name="Wraithlord", qty=1, unit_price=65.0, source="catalog"),
        Item(id=3, side="B", name="Wraithblade", qty=3, unit_price=13.0, source="catalog"),
    ]
    assert side_total(items, "A") == 150.0
    assert side_total(items, "B") == 39.0


def test_compute_balance_matches_discord_example():
    # From the real negotiation: 7 models totaling $224, described as "$11 short" of a $235 target.
    balance = compute_balance(total_a=224.0, total_b=0.0, cash_a=0, cash_b=235.0)
    assert balance.suggested_topup_side == "A"
    assert balance.suggested_topup_amount == 11.0


def test_compute_balance_already_balanced():
    balance = compute_balance(total_a=100.0, total_b=100.0)
    assert balance.suggested_topup_side is None
    assert balance.suggested_topup_amount == 0.0


def test_apply_condition():
    assert apply_condition(100.0, "needs_repair") == 80.0
    assert apply_condition(50.0, "showcase") == 70.0
    assert apply_condition(65.0, "assembled") == 65.0


def test_rebaseline_condition_recovers_true_base_not_the_discounted_price():
    # $100 true value -> needs_repair -> $80 stored. Switching to showcase must
    # apply 140% of the true $100, not 140% of the already-discounted $80
    # (which would wrongly give $112).
    assert rebaseline_condition(80.0, "needs_repair", "showcase") == 140.0


def test_rebaseline_condition_round_trip():
    price = apply_condition(100.0, "needs_repair")
    assert rebaseline_condition(price, "needs_repair", "assembled") == 100.0


def test_compute_totals_no_items_no_venue_no_commission():
    room = _room()
    totals = compute_totals(room)
    assert totals.total_a == 0.0
    assert totals.total_b == 0.0
    assert totals.venue_multiplier == 1.0
    assert totals.commission_amount == 0.0
    assert totals.suggested_topup_side is None


def test_compute_totals_folds_venue_differential_into_both_sides():
    items = [
        Item(id=1, side="A", name="Damaged Test Item", qty=1, unit_price=140.0, source="manual"),
        Item(id=2, side="B", name="Mint Test Item", qty=1, unit_price=70.0, source="manual"),
    ]
    room = _room(items=items, trade_venue="in_person", in_person_differential=0.20)
    totals = compute_totals(room)
    assert totals.venue_multiplier == 0.8
    assert totals.effective_side_a == 112.0
    assert totals.effective_side_b == 56.0


def test_compute_totals_folds_percentage_commission_into_owed_side():
    # Real scenario: painter (Side B) owed 40% of $500 MSRP = $200, no items yet.
    room = _room(commission_side="B", commission_type="percentage", commission_rate=0.40, commission_base=500)
    totals = compute_totals(room)
    assert totals.commission_amount == 200.0
    assert totals.effective_side_b == 200.0
    assert totals.suggested_topup_side == "A"
    assert totals.suggested_topup_amount == 200.0


def test_compute_totals_flat_commission():
    room = _room(commission_side="B", commission_type="flat", commission_flat_amount=150.0)
    totals = compute_totals(room)
    assert totals.commission_amount == 150.0


def test_compute_totals_no_commission_side_means_no_commission():
    room = _room(commission_side=None, commission_type="percentage", commission_rate=0.40, commission_base=500)
    totals = compute_totals(room)
    assert totals.commission_amount == 0.0
