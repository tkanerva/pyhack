"""Tests for core.pickup (the pickobj subset, PLAN-ARMOR.md Phase 2)."""

from core import PickupCommand, step
from core.events import MessageEvent
from core.mkobj import coarse_otype
from core.objects import OBJECTS, ObjType
from core.pickup import pickup
from core.types import Item, ObjectType
from conftest import SeqRng, assert_item_locations, make_world

HERO_POS = (6, 4)


def _floor(w, i, pos=HERO_POS, name=None) -> Item:
    it = Item(
        id=f"floor_{i}",
        otype=ObjectType.ARMOR,
        name=name if name is not None else f"item {i}",
        pos=pos,
    )
    w.items[it.id] = it
    return it


def _dagger(w, i, pos=HERO_POS) -> Item:
    """A dagger -- a real OBJECTS row, so it stacks (the otyp-0 items
    `_floor` builds never do: OBJECTS[0].oc_merge is false)."""
    otyp = int(ObjType.DAGGER)
    it = Item(
        id=f"dagger_{i}",
        otype=coarse_otype(otyp),
        name=OBJECTS[otyp].name,
        otyp=otyp,
        oclass=int(OBJECTS[otyp].oclass),
        pos=pos,
    )
    w.items[it.id] = it
    return it


def test_pickup_takes_topmost_item():
    w = make_world()
    first = _floor(w, 1)
    second = _floor(w, 2)
    ev = pickup(w, "player", SeqRng())
    # the most recently placed is C's chain head (documented)
    assert second.pos is None and second.carrier == "player"
    assert second in w.hero.inventory
    assert first.pos == HERO_POS  # the other one is still on the floor
    assert [e.text for e in ev] == ["You pick up the item 2."]
    assert_item_locations(w)


def test_pickup_empty_tile():
    w = make_world()
    ev = pickup(w, "player", SeqRng())
    assert [e.text for e in ev] == ["You see nothing here to pick up."]


def test_pickup_ignores_items_on_other_tiles():
    w = make_world()
    far = _floor(w, 1, pos=(8, 4))
    ev = pickup(w, "player", SeqRng())
    assert [e.text for e in ev] == ["You see nothing here to pick up."]
    assert far.pos == (8, 4) and far.carrier is None


def test_pickup_merges_a_duplicate_into_the_pack():
    """The merge half of addinv, reached through the floor: a second
    dagger joins the one already carried, so the pack keeps one stack and
    one letter -- while the line still names the object that was lying
    there (C: the picked object, before it merges)."""
    w = make_world()
    first = _dagger(w, 1)
    pickup(w, "player", SeqRng())
    assert first.carrier == "player" and first.invlet == "a"
    letter, lastinvnr = first.invlet, w.lastinvnr
    second = _dagger(w, 2)
    ev = pickup(w, "player", SeqRng())
    assert [e.text for e in ev] == ["You pick up the dagger."]
    assert w.hero.inventory == [first]
    assert first.quan == 2
    assert second.id not in w.items
    assert first.invlet == letter and w.lastinvnr == lastinvnr
    assert_item_locations(w)


def test_pickup_through_step():
    w = make_world()
    it = _floor(w, 1, name="elven leather helm")
    ev = step(w, PickupCommand(), SeqRng())
    assert it.pos is None and it.carrier == "player"
    assert it in w.hero.inventory
    assert it.invlet == "a"  # addinv letters the hero's pack
    assert_item_locations(w)
    assert any(
        isinstance(e, MessageEvent) and e.text == "You pick up the elven leather helm."
        for e in ev
    )
