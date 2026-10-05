"""Tests for core.props: intrinsic / extrinsic property queries.

The prop-system port (PLAN-ARMOR.md: the ``u.uprops[]`` work that
unlocks the ``<Type>_on()`` / ``<Type>_off()`` stubs in core.worn) is
not in yet, so this module SKIPS until core/props.py exists (a plain
import would otherwise break collection of the whole suite).  It pins
the API the port should expose:

- ``has_property(world, mon, prop)`` -- True when ``mon`` has the
  intrinsic ``prop`` (``mon.intrinsics``) or wears an item whose
  table row conveys it (the ``OBJECTS`` ``oprop`` over the worn gear,
  C's extrinsic bookkeeping).
- The intrinsic properties live on ``mon.intrinsics`` (a set of
  ``core.objects.Prop``; C's ``u.uprops[]`` bitmask, Pythonic).
  ``Monster`` gains the field with the port; until then the tests set
  it directly (plain dataclasses take the attribute).

The item builders use the real core.objects table (fine identity), the
test_worn.py pattern: coarse ``Item.otype`` from the fine oclass,
``Item.otyp`` / ``Item.oclass`` from the row, the worn state the
``Item.owornmask`` bitmask.
"""
import pytest

# the module under test: skip (not fail) until the prop-system port
pytest.importorskip("core.props",
                    reason="the prop-system port is not in yet "
                           "(PLAN-ARMOR.md)")

from core.objects import OBJECTS, ObjClass, ObjType, Prop  # noqa: E402
from core.objects import W_ARMC, W_RINGL  # noqa: E402
from core.props import has_property  # noqa: E402
from core.types import Item, ObjectType  # noqa: E402
from conftest import make_world  # noqa: E402

# fine oclass -> coarse ObjectType for the Item field (test_worn.py)
_COARSE = {
    int(ObjClass.ARMOR): ObjectType.ARMOR,
    int(ObjClass.RING): ObjectType.RING,
}


def _item(otyp: ObjType, owornmask: int = 0) -> Item:
    """A runtime Item with the fine identity of table row ``otyp``."""
    o = OBJECTS[otyp.value]
    oclass = int(o.oclass)
    return Item(
        id=f"it_{otyp.name.lower()}", otype=_COARSE[oclass],
        name=o.name or o.descr,
        otyp=otyp.value, oclass=oclass, owornmask=owornmask)


def _add(w, mon, item) -> Item:
    """Carry ``item`` in ``mon``'s inventory (and the world registry)."""
    item.container = mon.id
    mon.inventory.append(item)
    w.items[item.id] = item
    return item


def test_carried_but_not_worn_gives_nothing():
    w = make_world()
    hero = w.hero
    _add(w, hero, _item(ObjType.RIN_FIRE_RESISTANCE))
    assert not has_property(w, hero, Prop.FIRE_RES)


def test_worn_ring_gives_extrinsic_and_removal_takes_it_away():
    w = make_world()
    hero = w.hero
    ring = _add(w, hero, _item(ObjType.RIN_FIRE_RESISTANCE))
    ring.owornmask = W_RINGL
    assert has_property(w, hero, Prop.FIRE_RES)
    ring.owornmask = 0
    assert not has_property(w, hero, Prop.FIRE_RES)


def test_worn_cloak_gives_its_own_property_only():
    w = make_world()
    hero = w.hero
    _add(w, hero, _item(ObjType.ELVEN_CLOAK, owornmask=W_ARMC))
    assert has_property(w, hero, Prop.STEALTH)
    assert not has_property(w, hero, Prop.FIRE_RES)


def test_intrinsic_needs_no_item():
    w = make_world()
    hero = w.hero
    hero.intrinsics = set()  # Monster gains the field with the port
    assert not has_property(w, hero, Prop.COLD_RES)
    hero.intrinsics.add(Prop.COLD_RES)
    assert has_property(w, hero, Prop.COLD_RES)
