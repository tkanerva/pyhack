"""Tests for stacking and splitting -- PLAN-INVENT.md phase B
(`mergable` / `merge_choice` / `merged` / `stackobj` / `splittable`)
and PLAN-MKOBJ.md §3.6 (`splitobj` / `unsplitobj`).

C provenance (NetHack 5.0, local clone at ../NetHack): src/invent.c --
mergable (4429-4551), merged (812-948), merge_choice (771-810),
stackobj (4415-4427), splittable (1662-1668); src/mkobj.c -- splitobj
(456-503), unsplitobj (555-622).

Why one suite: a stack is ONE `Item` whose `quan` is the count, so
"may these two combine?" *is* the whole of stacking, and its answer is
read off a dozen fields.  Every rule test below turns exactly one field
on and pins the answer; the split tests pin the inverse direction.  The
three writers of `quan` (`merged` here, `mkobj.splitobj`, `useup`'s
decrement) have to agree, and `assert_item_locations` is the tripwire
that they still leave every object in exactly one place.

House convention: the items are hand-built over the REAL `OBJECTS` rows
(`_item`) rather than made with `mksobj`, because mksobj's own
randomisation (BUC, `spe`, quantity, erosion) would decide the answer
instead of the field under test.
"""

import pytest

from core.invent import (
    addinv,
    assigninvlet,
    delobj,
    merge_choice,
    mergable,
    merged,
    splittable,
    stackobj,
)
from core.mkobj import (
    add_to_container,
    coarse_otype,
    place_object,
    splitobj,
    unsplitobj,
    weight,
)
from core.monst import PM_GOBLIN, PM_KOBOLD, PM_TROLL
from core.objects import OBJECTS, ObjType, W_SWAPWEP, W_WEP
from core.types import Item, ObjectType
from core.worn import setworn
from conftest import assert_item_locations, make_hero, make_world

O = ObjType  # noqa: E741 -- the house alias for the object table

POS = (6, 4)


def _item(otyp: int, id: str, **kw) -> Item:
    """A hand-built item of a real OBJECTS row (every field at its C
    default except the ones the test is about)."""
    row = OBJECTS[otyp]
    return Item(
        id=id,
        otype=coarse_otype(otyp),
        name=kw.pop("name", row.name),
        otyp=otyp,
        oclass=int(row.oclass),
        **kw,
    )


def _world(*items: Item):
    """A world whose hero carries `items` (the state `make_world`
    builds: the pack is a list of the carried items)."""
    for it in items:
        it.carrier = "player"
    w = make_world(items=items)
    w.lev = 1
    return w


def _carry(w, item):
    """Put one more item in the hero's pack without going through
    addinv -- addinv merges a compatible stack, which is the very thing
    the unsplitobj tests are asking that function to do."""
    item.carrier = w.hero.id
    item.lev = w.hero.lev
    item.pos = None
    w.hero.inventory.append(item)
    w.items[item.id] = item


# ------------------------------------------------------------
# mergable -- the rule table (C: invent.c 4429-4551)
# ------------------------------------------------------------


def test_mergable_refuses_the_same_object():
    """C's first test is `obj == otmp`: an object never merges with
    itself."""
    dagger = _item(int(O.DAGGER), "a")
    assert not mergable(dagger, dagger)


def test_mergable_needs_the_same_otyp():
    assert not mergable(_item(int(O.DAGGER), "a"), _item(int(O.LONG_SWORD), "b"))


def test_mergable_follows_oc_merge():
    """A row that is not stackable at all is refused whatever the fields
    say: a container never merges (its contents are the identity), and
    neither does a demo-kit object (`otyp` 0, the C STRANGE_OBJECT row,
    whose `oc_merge` is false)."""
    assert not mergable(_item(int(O.SACK), "a"), _item(int(O.SACK), "b"))
    plain = Item(id="x", otype=ObjectType.TOOL, name="thing")
    other = Item(id="y", otype=ObjectType.TOOL, name="thing")
    assert not mergable(plain, other)


def test_coins_always_merge():
    """C returns TRUE for a coin before any BUC comparison -- money is
    money, so a blessed pile and a plain one are one pile."""
    assert mergable(
        _item(int(O.GOLD_PIECE), "a", quan=10),
        _item(int(O.GOLD_PIECE), "b", quan=5, blessed=True),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("blessed", True),
        ("cursed", True),
        ("spe", 1),
        ("unpaid", True),
        ("no_charge", True),
        ("broken", True),
        ("otrapped", True),
        ("dknown", True),
        ("oeroded", 1),
        ("oeroded2", 1),
        ("greased", True),
        ("oartifact", 1),
    ],
)
def test_mergable_refuses_one_differing_field(field, value):
    """Each of C's equality tests, one field at a time: two daggers that
    disagree on any of them stay two daggers (a +0 and a +1 blade, a
    blessed and an unblessed one, a rusty and a clean one, ...)."""
    assert not mergable(
        _item(int(O.DAGGER), "a"), _item(int(O.DAGGER), "b", **{field: value})
    )


def test_mergable_compares_erodeproof_only_when_erosion_matters():
    """C: `erosion_matters(obj) && obj->oerodeproof != otmp->oerodeproof`.
    A dagger erodes, so a rustproof one never joins a plain one; a potion
    does not erode, so its flag is never read."""
    assert not mergable(
        _item(int(O.DAGGER), "a"), _item(int(O.DAGGER), "b", oerodeproof=True)
    )
    assert mergable(
        _item(int(O.POT_HEALING), "c"),
        _item(int(O.POT_HEALING), "d", oerodeproof=True),
    )


def test_mergable_reads_oeaten_only_on_food():
    """C compares `oeaten` (how much of the meal is eaten) inside the
    FOOD_CLASS branch only -- a half-eaten ration does not join a whole
    one, but the same field on a non-food object means nothing."""
    assert not mergable(
        _item(int(O.FOOD_RATION), "a"), _item(int(O.FOOD_RATION), "b", oeaten=10)
    )
    assert mergable(_item(int(O.DAGGER), "c"), _item(int(O.DAGGER), "d", oeaten=10))


def test_mergable_needs_the_same_corpse_subject():
    """C: a CORPSE / EGG / TIN carries a monster type, and two different
    monsters are two different objects."""
    assert not mergable(
        _item(int(O.CORPSE), "a", corpsenm=PM_KOBOLD),
        _item(int(O.CORPSE), "b", corpsenm=PM_GOBLIN),
    )
    assert mergable(
        _item(int(O.CORPSE), "c", corpsenm=PM_KOBOLD),
        _item(int(O.CORPSE), "d", corpsenm=PM_KOBOLD),
    )


def test_a_revivable_corpse_never_merges():
    """C: "ditto for revivable corpses" -- a troll may get up again, so
    its corpse keeps its own identity even against an identical one."""
    assert not mergable(
        _item(int(O.CORPSE), "a", corpsenm=PM_TROLL),
        _item(int(O.CORPSE), "b", corpsenm=PM_TROLL),
    )


def test_mergable_allows_candles_only_in_the_same_25_turn_window():
    """C's magic 25 (see begin_burn): two candles burn at the same rate,
    so their ages must round to the same window -- otherwise the older
    one would silently inherit the younger one's fuel."""
    assert mergable(
        _item(int(O.TALLOW_CANDLE), "a", age=0),
        _item(int(O.TALLOW_CANDLE), "b", age=24),
    )
    assert not mergable(
        _item(int(O.TALLOW_CANDLE), "c", age=0),
        _item(int(O.TALLOW_CANDLE), "d", age=25),
    )


def test_mergable_refuses_a_different_name():
    """`Item.name` is the type name for everything mksobj builds, so this
    is C's `oname` comparison standing in: a named object does not join
    an otherwise identical unnamed one."""
    assert not mergable(
        _item(int(O.DAGGER), "a"), _item(int(O.DAGGER), "b", name="Sting")
    )


def test_mergable_is_a_pure_reading():
    """The rule table mutates nothing: asking the question twice costs
    nothing and changes nothing."""
    a = _item(int(O.DAGGER), "a", quan=2)
    b = _item(int(O.DAGGER), "b", quan=3)
    before = (a.quan, a.owt, b.quan, b.owt)
    assert mergable(a, b)
    assert mergable(a, b)
    assert (a.quan, a.owt, b.quan, b.owt) == before


# ------------------------------------------------------------
# merge_choice (C: invent.c 771-810)
# ------------------------------------------------------------


def test_merge_choice_answers_the_first_stack_that_takes_it():
    """C's walk down the chain: the first compatible stack wins (order
    is the pack's, not "the best match"), and no match is None."""
    pack = [_item(int(O.DAGGER), "a"), _item(int(O.DAGGER), "b")]
    new = _item(int(O.DAGGER), "c")
    assert merge_choice(pack, new) is pack[0]
    assert merge_choice([], new) is None
    assert merge_choice([_item(int(O.ARROW), "d")], new) is None


def test_merge_choice_punts_on_a_scare_monster_scroll():
    """C: "punt on these" -- a scroll of scare monster must not stack,
    because its count is the number of turns of protection left."""
    assert mergable(
        _item(int(O.SCR_SCARE_MONSTER), "a"),
        _item(int(O.SCR_SCARE_MONSTER), "b"),
    )
    assert (
        merge_choice(
            [_item(int(O.SCR_SCARE_MONSTER), "b")], _item(int(O.SCR_SCARE_MONSTER), "a")
        )
        is None
    )


# ------------------------------------------------------------
# merged (C: invent.c 812-948)
# ------------------------------------------------------------


def test_merged_sums_the_quantity_the_weight_and_the_age():
    """`quan` is the sum, `owt` follows it (weight() is the one formula),
    and the age is C's quantity-weighted average -- the whole reason a
    corpse stack keeps a sensible rot age."""
    a = _item(int(O.DAGGER), "a", quan=1, age=100)
    b = _item(int(O.DAGGER), "b", quan=3, age=200)
    w = _world(a, b)
    assert merged(w, a, b)
    assert a.quan == 4
    assert a.owt == weight(w, a) == 40  # a dagger is 10
    assert a.age == (100 * 1 + 200 * 3) // 4
    assert "b" not in w.items


def test_merged_deletes_the_loser_and_keeps_the_survivor_in_place():
    """C: obj_extract_self(obj) + obfree(obj) -- the loser leaves the
    pack and the world, the survivor keeps its slot and its letter."""
    a = _item(int(O.DAGGER), "a", invlet="c")
    b = _item(int(O.DAGGER), "b")
    w = _world(a, b)
    assert merged(w, a, b)
    assert w.hero.inventory == [a]
    assert a.invlet == "c"
    assert set(w.items) == {"a"}
    assert_item_locations(w)


def test_merged_teaches_the_survivor_that_its_enchantment_is_known():
    """C: "objects can be identified by comparing them" -- when one
    stack's enchantment was known and the other's was not, the survivor's
    is now known.  (mergable only refuses that pair when the hero is
    Blind, which the port's sighted branch skips; C also prints the
    comparison message, which this path has no message layer for.)"""
    a = _item(int(O.DAGGER), "a", known=False)
    b = _item(int(O.DAGGER), "b", known=True)
    w = _world(a, b)
    assert merged(w, a, b)
    assert a.known


def test_merged_refuses_and_changes_nothing_when_not_mergable():
    a = _item(int(O.DAGGER), "a")
    b = _item(int(O.DAGGER), "b", spe=1)
    w = _world(a, b)
    assert not merged(w, a, b)
    assert a.quan == 1 and b.quan == 1
    assert set(w.items) == {"a", "b"}
    assert w.hero.inventory == [a, b]


def test_merged_keeps_the_primary_weapon_slot():
    """C's "fixup for #adjust merging wielded darts, daggers, &c":
    primary weapon beats alternate weapon beats quiver, and the loser is
    unworn before it goes."""
    a = _item(int(O.DAGGER), "a")
    b = _item(int(O.DAGGER), "b")
    w = _world(a, b)
    setworn(w.hero, a, W_WEP)
    setworn(w.hero, b, W_SWAPWEP)
    assert merged(w, a, b)
    assert a.owornmask == W_WEP
    assert a.quan == 2
    assert b not in w.hero.inventory


def test_a_merge_costs_no_new_id():
    """Merging creates nothing, so the id allocator does not move (the
    counterpart of splitobj, which must)."""
    a = _item(int(O.DAGGER), "a")
    b = _item(int(O.DAGGER), "b")
    w = _world(a, b)
    before = w.ident
    assert merged(w, a, b)
    assert w.ident == before


# ------------------------------------------------------------
# stackobj (C: invent.c 4415-4427)
# ------------------------------------------------------------


def test_stackobj_merges_a_landed_object_into_the_floor_pile():
    """C's `merged(&obj, &otmp)`: the object that just landed absorbs the
    pile that was already there, so `stackobj` answers the newcomer and
    the square ends up with one stack."""
    w = _world()
    first = _item(int(O.DAGGER), "a", quan=2)
    place_object(w, first, POS, w.lev)
    second = _item(int(O.DAGGER), "b", quan=1)
    place_object(w, second, POS, w.lev)
    assert len(w.items_at(POS)) == 2
    survivor = stackobj(w, second)
    assert survivor is second
    assert second.quan == 3
    assert w.items_at(POS) == [second]
    assert "a" not in w.items
    assert_item_locations(w)


def test_stackobj_leaves_a_lone_item_alone():
    """Nothing compatible on the square: the object stays as it is (and
    an object that is not on the floor has nothing to merge into)."""
    w = _world()
    dagger = _item(int(O.DAGGER), "a")
    place_object(w, dagger, POS, w.lev)
    arrow = _item(int(O.ARROW), "b")
    place_object(w, arrow, POS, w.lev)
    assert stackobj(w, arrow) is arrow
    assert len(w.items_at(POS)) == 2
    free = _item(int(O.DAGGER), "c")
    assert stackobj(w, free) is free


# ------------------------------------------------------------
# splittable (C: invent.c 1662-1668)
# ------------------------------------------------------------


def test_splittable_refuses_a_cursed_loadstone():
    """A cursed loadstone is welded to the floor of the pack by weight,
    so a count prefix may not take part of it."""
    assert not splittable(_item(int(O.LOADSTONE), "a", cursed=True, quan=2))
    assert splittable(_item(int(O.LOADSTONE), "b", quan=2))


def test_splittable_refuses_a_cursed_wielded_weapon():
    """C reads `welded(uwep)`; there is no wield module yet, so the port
    stands in with "cursed and in the primary weapon slot"."""
    hero = make_hero()
    wielded = _item(int(O.DAGGER), "a", cursed=True, quan=3, owornmask=W_WEP)
    assert not splittable(wielded, hero)
    wielded.cursed = False
    assert splittable(wielded, hero)
    # cursed but not wielded: nothing welds it
    assert splittable(_item(int(O.DAGGER), "b", cursed=True, quan=3), hero)


# ------------------------------------------------------------
# splitobj (C: mkobj.c 456-503)
# ------------------------------------------------------------


def test_splitobj_moves_the_quantity_and_the_weight():
    w = _world()
    arrows = _item(int(O.ARROW), "a", quan=10)
    arrows.owt = weight(w, arrows)
    w.items[arrows.id] = arrows
    child = splitobj(w, arrows, 3)
    assert arrows.quan == 7 and child.quan == 3
    assert child.id != arrows.id
    assert arrows.owt == weight(w, arrows) == 7
    assert child.owt == weight(w, child) == 3
    assert set(w.items) == {"a", child.id}


def test_splitobj_hands_back_a_free_child():
    """C links the child into the parent's chain (`obj->nobj = otmp`).
    This port answers a *free* object instead -- the same state mksobj
    answers -- because the pack list is core.invent's alone; the caller
    places it (addinv, place_object, the throw's flight)."""
    w = _world()
    parent = _item(int(O.ARROW), "a", quan=5)
    w.items[parent.id] = parent
    child = splitobj(w, parent, 2)
    assert child.pos is None and child.carrier is None
    assert child.contents == [] and child.contents is not parent.contents


def test_splitobj_keeps_the_parents_letter_and_records_the_pair():
    """The plan's rule (PLAN-THROW phase C.1): the parent keeps its
    letter, the child is a new id from the World's allocator, and the
    (parent, child) pair is remembered for unsplitobj -- C's
    svc.context.objsplit, which holds exactly one pair."""
    w = _world()
    parent = _item(int(O.ARROW), "a", quan=4)
    _carry(w, parent)
    assigninvlet(w, w.hero, parent)
    letter = parent.invlet
    child = splitobj(w, parent, 1)
    assert parent.invlet == letter
    assert child.invlet == ""
    assert (w.split_parent, w.split_child) == (parent.id, child.id)


def test_splitobj_copies_every_identity_field():
    """C's `*otmp = *obj` struct copy: the child is the same object in
    every respect except the id, the quantity, the weight and the worn
    slot -- including an enchantment, a BUC state, erosion and the age."""
    w = _world()
    parent = _item(int(O.DAGGER), "a", quan=6, spe=2, blessed=True, oeroded=1, age=42)
    w.items[parent.id] = parent
    child = splitobj(w, parent, 2)
    assert (child.otyp, child.spe, child.blessed, child.oeroded) == (
        int(O.DAGGER),
        2,
        True,
        1,
    )
    assert child.age == 42
    assert child.owornmask == 0


def test_splitobj_refuses_what_c_panics_on():
    """C panics on a container (contents are the identity), on a
    non-positive count, and on a split that would empty the stack (the
    caller must use useup / delobj for that)."""
    w = _world()
    box = _item(int(O.CHEST), "box")
    place_object(w, box, POS, w.lev)
    add_to_container(w, box, _item(int(O.DAGGER), "in"))
    with pytest.raises(ValueError):
        splitobj(w, box, 1)
    single = _item(int(O.DAGGER), "one", quan=1)
    w.items[single.id] = single
    with pytest.raises(ValueError):
        splitobj(w, single, 1)  # quan <= num
    stack = _item(int(O.DAGGER), "two", quan=5)
    w.items[stack.id] = stack
    with pytest.raises(ValueError):
        splitobj(w, stack, 0)
    with pytest.raises(ValueError):
        splitobj(w, stack, -1)


# ------------------------------------------------------------
# unsplitobj (C: mkobj.c 555-622)
# ------------------------------------------------------------


def test_unsplitobj_puts_a_split_stack_back_together():
    """The round trip: three arrows off a stack of ten, the child back in
    the same pack, and unsplitobj() recombines them into one stack.

    C's splitobj already linked the child into that list, so the state
    exists by construction there; this port's splitobj answers a free
    child, so the pair is put in the pack by hand -- which is the state
    a cancelled volley's re-add produces.
    """
    w = _world()
    arrows = _item(int(O.ARROW), "a", quan=10)
    _carry(w, arrows)
    child = splitobj(w, arrows, 3)
    _carry(w, child)
    back = unsplitobj(w, arrows)
    assert back is arrows
    assert arrows.quan == 10
    assert arrows.owt == weight(w, arrows) == 10
    assert child.id not in w.items
    assert w.hero.inventory == [arrows]
    assert_item_locations(w)


def test_unsplitobj_answers_none_for_a_floor_or_free_object():
    """C follows `o->nobj`, which only a carried or contained object has:
    a floor object (its chain is the square, not a pack) and a free
    object are both refused."""
    w = _world()
    on_floor = _item(int(O.DAGGER), "a", quan=2)
    place_object(w, on_floor, POS, w.lev)
    assert unsplitobj(w, on_floor) is None
    free = _item(int(O.DAGGER), "b", quan=2)
    w.items[free.id] = free
    assert unsplitobj(w, free) is None


def test_unsplitobj_refuses_halves_that_are_not_in_the_same_list():
    """The two ids must still be in ONE place (C scans the single list it
    derived from the object it was handed): a child left on the floor
    does not rejoin a parent in the pack."""
    w = _world()
    arrows = _item(int(O.ARROW), "a", quan=10)
    _carry(w, arrows)
    child = splitobj(w, arrows, 3)
    place_object(w, child, POS, w.lev)
    assert unsplitobj(w, arrows) is None
    assert arrows.quan == 7


def test_unsplitobj_answers_none_once_the_child_is_gone():
    w = _world()
    arrows = _item(int(O.ARROW), "a", quan=10)
    _carry(w, arrows)
    child = splitobj(w, arrows, 3)
    _carry(w, child)
    assert delobj(w, child.id) is child
    assert unsplitobj(w, arrows) is None
    assert arrows.quan == 7


def test_unsplitobj_ignores_an_item_that_is_not_half_of_the_split():
    """C keeps one pair; any other object is not it."""
    w = _world()
    arrows = _item(int(O.ARROW), "a", quan=10)
    _carry(w, arrows)
    child = splitobj(w, arrows, 3)
    _carry(w, child)
    other = _item(int(O.ARROW), "b", quan=2)
    _carry(w, other)
    assert unsplitobj(w, other) is None
    assert arrows.quan == 7 and other.quan == 2


def test_unsplitobj_answers_none_before_any_split():
    w = _world()
    item = _item(int(O.ARROW), "a", quan=10)
    _carry(w, item)
    assert unsplitobj(w, item) is None


# ------------------------------------------------------------
# the two merge points: addinv (the pack) and add_to_container
# ------------------------------------------------------------


def test_addinv_merges_into_the_pack_and_costs_no_letter():
    """C's addinv walks the chain with merged(&otmp, &obj): the newcomer
    joins the compatible stack, the survivor keeps its letter, the pack
    does not grow and no letter is spent."""
    w = _world()
    first = addinv(w, w.hero.id, _item(int(O.ARROW), "a", quan=2))
    letter, lastinvnr = first.invlet, w.lastinvnr
    second = addinv(w, w.hero.id, _item(int(O.ARROW), "b", quan=3))
    assert second is first
    assert first.quan == 5
    assert first.owt == weight(w, first) == 5
    assert first.invlet == letter
    assert w.lastinvnr == lastinvnr
    assert w.hero.inventory == [first]
    assert set(w.items) == {first.id}
    assert_item_locations(w)


def test_addinv_keeps_two_stacks_that_may_not_merge():
    """A +0 and a +1 dagger are two items with two letters; the merge
    walk is a test, not a fiat."""
    w = _world()
    plain = addinv(w, w.hero.id, _item(int(O.DAGGER), "a"))
    magic = addinv(w, w.hero.id, _item(int(O.DAGGER), "b", spe=1))
    assert plain is not magic
    assert len(w.hero.inventory) == 2
    assert plain.invlet != magic.invlet


def test_add_to_container_merges_compatible_stacks():
    """C's add_to_container walks `container->cobj` with merged(), so a
    chest's two identical daggers are one stack and the container's
    weight follows."""
    w = _world()
    box = _item(int(O.CHEST), "box")
    place_object(w, box, POS, w.lev)
    first = _item(int(O.DAGGER), "a", quan=1)
    second = _item(int(O.DAGGER), "b", quan=2)
    assert add_to_container(w, box, first) is first
    assert add_to_container(w, box, second) is first
    assert box.contents == [first.id]
    assert first.quan == 3
    assert box.owt == weight(w, box)
    assert "b" not in w.items
    assert_item_locations(w)


def test_add_to_container_keeps_incompatible_items_apart():
    w = _world()
    box = _item(int(O.CHEST), "box")
    place_object(w, box, POS, w.lev)
    first = add_to_container(w, box, _item(int(O.DAGGER), "a"))
    second = add_to_container(w, box, _item(int(O.DAGGER), "b", spe=1))
    assert box.contents == [first.id, second.id]
    assert_item_locations(w)
