"""Tests for core.invent -- the pack, its letters, and the one writer
of "where is this item" (PLAN-INVENT.md phase A).

C provenance (NetHack 5.0, local clone at ../NetHack): src/invent.c --
assigninvlet (693-732), invletter_value (391-399), reorder_invent
(738-767), obj_to_let (2902-2909), let_to_name (4852-4891), addinv /
addinv_core0 (1151-1155, 1055-1148), freeinv (1402-1409), useup
(1320-1333), useupall (1311-1317), delobj / delobj_core (1429-1462),
consume_obj_charge (1336-1346), carry_obj_effects (1186-1196).

House conventions: every test asserts world state *and*, where the
function returns one, the value; the `assert_item_locations` invariant
runs after every mutation the pack half makes.
"""
import pytest

from core.invent import (CONTAINED_SYM, GOLD_SYM, NOINVSYM, addinv,
                         assigninvlet, carry_obj_effects,
                         consume_obj_charge, delobj, freeinv,
                         invletter_value, let_to_name, obj_to_let,
                         reorder_invent, useup, useupall)
from core.mkobj import add_to_container, place_object, weight
from core.objects import MAXOCLASSES, ObjClass
from core.pickup import pickup
from core.types import Item, ObjectType
from conftest import SeqRng, assert_item_locations, make_world

HERO_POS = (6, 4)


def thing(id="thing_0", otype=ObjectType.ARMOR, name="thing", **kw):
    """A loose hand-built item (the demo-kit convention: no fine
    identity, so `name` is what the messages say)."""
    return Item(id=id, otype=otype, name=name, **kw)


def floor(w, item, pos=HERO_POS):
    place_object(w, item, pos, w.lev)
    return item


# ------------------------------------------------------------
# invletter_value -- the C rank table
# ------------------------------------------------------------

@pytest.mark.parametrize("letter,value", [
    ("$", 1),            # GOLD_SYM
    ("a", 2), ("z", 2 + 25),
    ("A", 2 + 26), ("Z", 2 + 26 + 25),
    ("#", 1 + 52 + 1),   # NOINVSYM
    ("!", 1 + 52 + 2),   # C: none of the above
    ("", 1 + 52 + 2),    # the pyhack empty letter hits the catchall
])
def test_invletter_value_ranks(letter, value):
    """C: invletter_value -- '$'==1, 'a'-'z'==2..27, 'A'-'Z'==28..53,
    '#'==54, catchall 55."""
    assert invletter_value(letter) == value


# ------------------------------------------------------------
# assigninvlet -- the a..z A..Z '#' allocation
# ------------------------------------------------------------

def test_first_letter_is_a():
    """C: the walk starts at lastinvnr + 1, and reset_globals leaves
    lastinvnr at -1 -- so the first letter is 'a'."""
    w = make_world()
    it = addinv(w, "player", thing())
    assert it.invlet == "a"
    assert w.lastinvnr == 0
    assert obj_to_let(it) == "a"


def test_letters_are_allocated_in_order():
    w = make_world()
    letters = [addinv(w, "player", thing(id=f"t{i}")).invlet
               for i in range(4)]
    assert letters == ["a", "b", "c", "d"]
    assert w.lastinvnr == 3


def test_a_full_pack_gets_noinvsym():
    """C: every one of the 52 letters taken -> NOINVSYM ('#'), and the
    walk cannot loop (the C `inuse[i] ? NOINVSYM` answer)."""
    w = make_world()
    items = [addinv(w, "player", thing(id=f"t{i}")) for i in range(52)]
    assert items[-1].invlet == "Z"          # a..z, then A..Z
    assert {it.invlet for it in items} == \
        set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    overflow = addinv(w, "player", thing(id="t52"))
    assert overflow.invlet == NOINVSYM


def test_the_coin_stack_is_always_gold_sym():
    """C: the COIN_CLASS early return -- there is at most one gold
    pile in the pack."""
    w = make_world()
    gold = thing(id="gold_0", otype=ObjectType.COIN, name="gold piece",
                 oclass=ObjClass.COIN.value, quan=200)
    addinv(w, "player", gold)
    assert gold.invlet == GOLD_SYM
    assert w.lastinvnr == -1        # the walk never ran


def test_a_kept_letter_survives_a_re_pickup():
    """The letter-drift fix (PLAN-INVENT.md §2.2 defect 1): a letter
    is assigned once.  Drop the SECOND item and pick it up again -- the
    third item must keep the letter the player learned for it, where
    the old index-based UI re-lettered the whole tail of the pack."""
    w = make_world()
    first = addinv(w, "player", thing(id="t_0", name="apple",
                                      otype=ObjectType.FOOD))
    second = addinv(w, "player", thing(id="t_1", name="orange",
                                       otype=ObjectType.FOOD))
    third = addinv(w, "player", thing(id="t_2", name="melon",
                                      otype=ObjectType.FOOD))
    assert (first.invlet, second.invlet, third.invlet) == ("a", "b", "c")

    freeinv(w, "player", second)
    assert_item_locations(w)
    assert second.pos == HERO_POS and second.carrier is None
    assert [it.invlet for it in w.hero.inventory] == ["a", "c"]

    top = addinv(w, "player", second)
    assert top is second
    # C: invlet_constant -- the survivor keeps its learned letter, and
    # nothing else moves
    assert second.invlet == "b"
    assert [it.invlet for it in w.hero.inventory] == ["a", "b", "c"]
    assert [it.id for it in w.hero.inventory] == ["t_0", "t_1", "t_2"]
    assert_item_locations(w)


def test_a_colliding_letter_is_cleared_first():
    """C: the collision branch -- a letter held by ANOTHER item is
    dropped before the walk (the re-created item case)."""
    w = make_world()
    holder = addinv(w, "player", thing(id="t_0"))
    assert holder.invlet == "a"
    clone = thing(id="t_1", invlet="a")
    assigninvlet(w, w.hero, clone)
    assert holder.invlet == "a"         # the first one keeps it
    assert clone.invlet == "b"          # the newcomer is re-lettered
    assert w.lastinvnr == 1


def test_lastinvnr_walks_forward_and_wraps():
    """C: the walk starts just after gl.lastinvnr, so a freed letter
    EARLY in the alphabet is not reused while later ones are free."""
    w = make_world()
    a = addinv(w, "player", thing(id="t_0"))
    b = addinv(w, "player", thing(id="t_1"))
    assert (a.invlet, b.invlet) == ("a", "b")
    freeinv(w, "player", b)
    c = addinv(w, "player", thing(id="t_2"))
    assert c.invlet == "c"              # not the freed 'b'
    assert w.lastinvnr == 2


def test_a_monster_pack_carries_no_letters():
    """C: assigninvlet runs on gi.invent, the HERO's pack -- a
    monster's minvent has no letters (addinv skips the letter half)."""
    from conftest import make_monster
    w = make_world(monsters=[make_monster()])
    it = addinv(w, "goblin_0", thing())
    assert it.invlet == ""
    assert w.lastinvnr == -1


# ------------------------------------------------------------
# reorder_invent / obj_to_let
# ------------------------------------------------------------

def test_reorder_invent_sorts_by_the_inv_rank_key():
    """C: reorder_invent -- inv_rank is `invlet ^ 040`, i.e. '#' and
    '$' first, then a..z, then A..Z."""
    w = make_world()
    items = [thing(id="i0", invlet="B"), thing(id="i1", invlet="a"),
             thing(id="i2", invlet="A"), thing(id="i3", invlet="z"),
             thing(id="i4", invlet=GOLD_SYM), thing(id="i5", invlet="b"),
             thing(id="i6", invlet=NOINVSYM)]
    w.hero.inventory = list(items)
    reorder_invent(w.hero)
    assert [it.invlet for it in w.hero.inventory] == \
        ["#", "$", "a", "b", "z", "A", "B"]


def test_obj_to_let_is_the_stored_letter():
    """C: obj_to_let -- with invlet_constant (unconditional here) the
    item's own letter is the answer."""
    assert obj_to_let(thing(invlet="q")) == "q"


# ------------------------------------------------------------
# let_to_name -- the C names[] table
# ------------------------------------------------------------

def test_let_to_name_is_the_c_table():
    """C: names[] (invent.c 4841-4845), indexed by the oclass id."""
    assert let_to_name(int(ObjClass.WEAPON)) == "Weapons"
    assert let_to_name(int(ObjClass.ARMOR)) == "Armor"
    assert let_to_name(int(ObjClass.FOOD)) == "Comestibles"
    assert let_to_name(int(ObjClass.POTION)) == "Potions"
    assert let_to_name(int(ObjClass.SCROLL)) == "Scrolls"
    assert let_to_name(int(ObjClass.SPBOOK)) == "Spellbooks"
    assert let_to_name(int(ObjClass.WAND)) == "Wands"
    assert let_to_name(int(ObjClass.COIN)) == "Coins"
    assert let_to_name(int(ObjClass.GEM)) == "Gems/Stones"
    assert let_to_name(int(ObjClass.ROCK)) == "Boulders/Statues"


def test_let_to_name_the_pseudo_letters():
    """C: oth_symbols / oth_names -- CONTAINED_SYM is "Bagged/Boxed
    items", and the catchall is ILLOBJ_CLASS's name."""
    assert let_to_name(ord(CONTAINED_SYM)) == "Bagged/Boxed items"
    assert let_to_name(0) == "Illegal objects"
    assert let_to_name(ord("!")) == "Illegal objects"


def test_let_to_name_unpaid_and_the_glyph_suffix():
    """C: the "Unpaid " prefix, and the showsym padding
    (invbuf_sympadding 8 -- `7 - len` spaces, then `  ('%c')`)."""
    assert let_to_name(int(ObjClass.COIN), unpaid=True) \
        == "Unpaid Coins"
    assert let_to_name(int(ObjClass.WEAPON), showsym=True) == "Weapons  (')')"
    # "Comestibles" is 11 wide: no padding at all (the C loop's
    # `while (--mlen > 0)` never runs)
    assert let_to_name(int(ObjClass.FOOD), showsym=True) \
        == "Comestibles  ('%')"
    # the two pseudo-letters never take a glyph (C: `oclass != 0`)
    assert let_to_name(ord(CONTAINED_SYM), showsym=True) \
        == "Bagged/Boxed items"


def test_the_class_table_covers_the_oclass_space():
    """The table is as long as the class space, so let_to_name can
    never answer a stale index."""
    for oclass in range(1, MAXOCLASSES):
        assert let_to_name(oclass)


# ------------------------------------------------------------
# addinv -- the pack half of the where-state
# ------------------------------------------------------------

def test_addinv_registers_and_marks_the_carrier():
    w = make_world()
    it = addinv(w, "player", thing())
    assert it.carrier == "player"
    assert it.pos is None
    assert it.lev == w.hero.lev
    assert it in w.hero.inventory
    assert w.items[it.id] is it
    assert_item_locations(w)


def test_addinv_extracts_the_item_from_the_floor():
    """C: the pickup path calls obj_extract_self() before addinv's
    `obj->where != OBJ_FREE` panic; here clearing `pos` IS the
    extract, so pickup works through addinv unchanged."""
    w = make_world()
    it = floor(w, thing())
    assert it.pos == HERO_POS
    assert pickup(w, "player", SeqRng()) is not None
    assert it.carrier == "player" and it.pos is None
    assert it.invlet == "a"
    assert_item_locations(w)


def test_addinv_refuses_an_item_that_is_already_carried():
    w = make_world()
    it = addinv(w, "player", thing())
    with pytest.raises(ValueError, match="already carried"):
        addinv(w, "player", it)


def test_addinv_refuses_an_item_inside_a_container():
    w = make_world()
    box = thing(id="box_0", name="chest")
    chest_item = thing(id="t_0")
    w.items[box.id] = box
    w.items[chest_item.id] = chest_item
    add_to_container(w, box, chest_item)
    with pytest.raises(ValueError, match="is inside"):
        addinv(w, "player", chest_item)


# ------------------------------------------------------------
# freeinv -- pack -> floor (C freeinv + the drop path's place_object)
# ------------------------------------------------------------

def test_freeinv_puts_the_item_on_the_carrier_s_square():
    w = make_world()
    it = addinv(w, "player", thing())
    freeinv(w, "player", it)
    assert it.carrier is None
    assert it.pos == HERO_POS
    assert it not in w.hero.inventory
    assert w.items[it.id] is it
    assert it.owornmask == 0        # C: freeinv leaves the mask alone
    assert_item_locations(w)


# ------------------------------------------------------------
# useup / useupall / delobj -- the three deletion paths
# ------------------------------------------------------------

def test_useup_takes_one_from_a_stack():
    """C: useup -- quan-- and a fresh weight; the item stays."""
    w = make_world()
    it = addinv(w, "player", thing(quan=3, owt=30))
    useup(w, "player", it)
    assert it.quan == 2
    assert it in w.hero.inventory
    assert w.items[it.id] is it
    assert it.owt == weight(w, it)      # C: obj->owt = weight(obj)
    assert it.owt != 30
    assert_item_locations(w)


def test_useup_removes_the_last_one():
    """C: the quan == 1 case is useupall -- setnotworn + freeinv +
    obfree."""
    w = make_world()
    it = addinv(w, "player", thing())
    useup(w, "player", it)
    assert w.items.get(it.id) is None
    assert it not in w.hero.inventory
    assert_item_locations(w)


def test_useupall_deletes_the_whole_stack():
    w = make_world()
    it = addinv(w, "player", thing(quan=5))
    useupall(w, "player", it)
    assert w.items.get(it.id) is None
    assert it not in w.hero.inventory


def test_delobj_finds_the_item_wherever_it_is():
    """C: delobj is the "from anywhere" delete -- floor, pack or
    container."""
    w = make_world()
    carried = addinv(w, "player", thing(id="t_0"))
    on_floor = floor(w, thing(id="t_1"), pos=(3, 3))
    box = floor(w, thing(id="box_0", name="chest"), pos=(4, 3))
    inside = thing(id="t_2")
    w.items[inside.id] = inside
    add_to_container(w, box, inside)

    assert delobj(w, carried.id) is carried
    assert delobj(w, on_floor.id) is on_floor
    assert delobj(w, inside.id) is inside
    assert carried.id not in w.items
    assert on_floor.id not in w.items
    assert inside.id not in w.items
    assert inside.id not in box.contents
    assert delobj(w, "nope") is None
    assert_item_locations(w)


def test_delobj_takes_the_contents_with_it():
    """C: obfree "deletes contents also" -- a chest's loot goes with
    the chest (the leak the old consume_item left behind)."""
    w = make_world()
    box = thing(id="box_0", name="chest")
    loot = [thing(id="t_0", name="gem"), thing(id="t_1", name="scroll")]
    floor(w, box, pos=(3, 3))
    for it in loot:
        w.items[it.id] = it
        add_to_container(w, box, it)
    assert_item_locations(w)

    delobj(w, box.id)
    assert w.items == {}
    assert not box.contents


def test_delobj_clears_the_worn_slot():
    """The single clearing point: a destroyed worn item cannot leave a
    slot bit the which_armor scan would answer for."""
    from core.objects import W_ARM
    from core.worn import which_armor
    w = make_world()
    mail = addinv(w, "player", thing(id="t_0", name="chain mail"))
    mail.owornmask = W_ARM
    delobj(w, mail.id)
    assert mail.owornmask == 0
    assert which_armor(w, w.hero, W_ARM) is None


def test_delobj_leaves_the_wielded_field_alone():
    """Documented divergence: ``Monster.wielded`` is not cleared here
    (core.items.wielded_of reads a dangling id as bare hands) --
    PLAN-DROP phase C replaces the field with wield.setuwep."""
    w = make_world()
    sword = addinv(w, "player", thing(id="t_0", name="short sword",
                                      otype=ObjectType.WEAPON))
    w.hero.wielded = sword.id
    delobj(w, sword.id)
    assert w.hero.wielded == sword.id


# ------------------------------------------------------------
# consume_obj_charge / carry_obj_effects
# ------------------------------------------------------------

def test_consume_obj_charge_spends_one_spe():
    """C: consume_obj_charge -- the `spe` decrement (the wand / book /
    tool charge), with the shop's maybe_unpaid accepted and ignored."""
    w = make_world()
    wand = addinv(w, "player", thing(id="t_0", otype=ObjectType.WAND,
                                     name="wand", spe=3))
    consume_obj_charge(w, "player", wand)
    assert wand.spe == 2
    consume_obj_charge(w, "player", wand, maybe_unpaid=True)
    assert wand.spe == 1


def test_carry_obj_effects_is_the_no_op_hook():
    """STUB: C's cursed-figurine transform timeout needs timeout.c --
    the call site stays, the body does nothing."""
    assert carry_obj_effects(thing()) is None


# ------------------------------------------------------------
# The invariant over a real world
# ------------------------------------------------------------

def test_the_demo_world_satisfies_the_invariant():
    """The starting kit and the floor kit go through addinv /
    place_object, so a fresh world is already consistent -- and the
    heroes' pack is lettered a..e."""
    import random
    from core.worldgen import new_world
    w = new_world(random.Random(42))
    assert_item_locations(w)
    assert [it.invlet for it in w.hero.inventory] == ["a", "b", "c", "d", "e"]
    assert [it.id for it in w.hero.inventory] == \
        ["sword_0", "mail_0", "cloak_0", "gloves_0", "ring_0"]
    floor_ids = {it.id for it in w.items.values() if it.pos is not None}
    assert "wand_0" in floor_ids and "food_3" in floor_ids


def test_pickup_and_useup_keep_the_invariant():
    import random
    from core.worldgen import new_world
    w = new_world(random.Random(42))
    hero = w.hero
    for _ in range(5):
        pickup(w, "player", SeqRng())
        assert_item_locations(w)
    held = [it for it in hero.inventory if it.invlet and it.invlet != GOLD_SYM]
    for it in list(held):
        useup(w, "player", it)
        assert_item_locations(w)
    assert not hero.inventory
