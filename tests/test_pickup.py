"""Tests for core.pickup (the pickobj subset, PLAN-ARMOR.md Phase 2)."""
from core import PickupCommand, step
from core.events import MessageEvent
from core.pickup import pickup
from core.types import Item, ObjectType
from conftest import SeqRng, make_world

HERO_POS = (6, 4)


def _floor(w, i, pos=HERO_POS, name=None) -> Item:
    it = Item(id=f"floor_{i}", otype=ObjectType.ARMOR,
              name=name if name is not None else f"item {i}", pos=pos)
    w.items[it.id] = it
    return it


def test_pickup_takes_topmost_item():
    w = make_world()
    first = _floor(w, 1)
    second = _floor(w, 2)
    ev = pickup(w, "player", SeqRng())
    # the most recently placed is C's chain head (documented)
    assert second.pos is None and second.container == "player"
    assert second in w.hero.inventory
    assert first.pos == HERO_POS  # the other one is still on the floor
    assert [e.text for e in ev] == ["You pick up the item 2."]


def test_pickup_empty_tile():
    w = make_world()
    ev = pickup(w, "player", SeqRng())
    assert [e.text for e in ev] == ["You see nothing here to pick up."]


def test_pickup_ignores_items_on_other_tiles():
    w = make_world()
    far = _floor(w, 1, pos=(8, 4))
    ev = pickup(w, "player", SeqRng())
    assert [e.text for e in ev] == ["You see nothing here to pick up."]
    assert far.pos == (8, 4) and far.container is None


def test_pickup_through_step():
    w = make_world()
    it = _floor(w, 1, name="elven leather helm")
    ev = step(w, PickupCommand(), SeqRng())
    assert it.pos is None and it.container == "player"
    assert it in w.hero.inventory
    assert any(isinstance(e, MessageEvent)
               and e.text == "You pick up the elven leather helm."
               for e in ev)
