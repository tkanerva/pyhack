"""Tests for the shop (core.mkroom.mkshop + core.shk) -- PLAN-SPECIAL-
ROOMS.md phase 4a.

What must hold: the shop-type table is the C one (12 rows, the
probabilities sum to 100, the four "unique" shops at 0); mkshop claims
the first ordinary, staircase-free, single-door room with a valid shape
-- lighting it, rolling the type from the table and downgrading a big
room's wand / book shop to a general store -- and sets rtype +
FILL_NORMAL without creating anything; stock_room then puts a peaceful
shopkeeper just inside the door (Eshk filled, Room.resident set, a
purse of 1000 + 30 * rnd(100)), repairs the doorway (no door -> open,
secret -> real, trapped -> locked + the "Closed for inventory" sign on
the corridor side), and stocks one object per free square -- every
square of the room except the row the door stands on.
"""

from typing import List, Tuple

from core import mkroom, shk
from core.commands import MoveCommand, PayCommand, TalkCommand, WaitCommand
from core.events import MessageEvent
from core.hacklib import distmin
from core.invent import addinv, money_cnt
from core.mklev import add_door, add_room, blank_map, makelevel, topologize
from core.mkobj import coarse_otype, place_object
from core.monst import MONS
from core.monst_defs import PM_SHOPKEEPER, S_MIMIC
from core.objects import BASES, NUM_OBJECTS, OBJECTS, O, ObjClass, W_ARMC
from core.rnd import Rng
from core.shknam_data import (
    FODDER_SHOP,
    SHKARMORS,
    SHOPTYPES,
    UNIQUE_SHOP_START,
    VEGETARIAN_CLASS,
)
from core.step import step
from core.types import (
    ANY_SHOP,
    BillEntry,
    Eshk,
    FILL_NORMAL,
    HungerState,
    Item,
    NO_ROOM,
    DoorMask,
    Map,
    Pos,
    Room,
    RoomType,
    ScrollType,
    Stairway,
    TerrainType,
    Tile,
    World,
)
from core.vision import vision_recalc
from conftest import assert_item_locations, make_hero, make_monster

W, H = 40, 20
LX, LY, HX, HY = 5, 4, 14, 10  # a 10x7 floor: 70 squares
DOOR = (LX, LY - 1)  # the door in the top wall
STOCKED = 60  # 70 minus the row under the top-wall door


def _rng(seed: int = 1) -> Rng:
    return Rng(b"shop-test:%d" % seed)


class _FixedRng:
    """A stand-in rng that answers `rnd` with one fixed value.

    mkshop's shop-type roll and get_shop_item's item-kind roll are the
    only draws either function makes, so one number is enough to pin
    which row of the table a test walks into.
    """

    def __init__(self, rnd_value: int) -> None:
        self.rnd_value = rnd_value

    def rnd(self, n: int) -> int:
        assert 1 <= self.rnd_value <= n
        return self.rnd_value

    def rn2(self, n: int) -> int:
        return 0

    def rn1(self, n: int, x: int) -> int:
        return x


def _room_map(
    door: bool = True,
    mask: DoorMask = DoorMask.CLOSED,
    typ: TerrainType = TerrainType.DOOR,
    lit: bool = True,
    box: Tuple[int, int, int, int] = (LX, LY, HX, HY),
) -> Tuple[Map, Room]:
    """One room with a door in the middle of its top wall."""
    lx, ly, hx, hy = box
    m = blank_map(W, H)
    room = add_room(m, lx, ly, hx, hy, lit, RoomType.OROOM, False)
    topologize(m, room)
    if door:
        wall = m.tiles[ly - 1][lx]
        m.tiles[ly - 1][lx] = Tile(
            typ=typ,
            door_mask=mask,
            roomno=wall.roomno,
            edge=wall.edge,
            lit=wall.lit,
        )
        add_door(m, lx, ly - 1, room)
    return m, room


def _world(m: Map, lev: int = 1) -> World:
    w = World(map=m)
    w.lev = lev
    w.actors["player"] = make_hero(pos=(1, 1))
    return w


def _kid(w: World, room: Room):
    mon = shk.room_keeper(w, room)
    assert mon is not None
    return mon


def _floor_items(w: World, lev: int) -> List:
    return [it for it in w.items.values() if it.lev == lev and it.pos is not None]


def _mons(w: World, lev: int) -> List:
    return [a for a in w.actors.values() if not a.is_hero and a.lev == lev]


def _purse(mon) -> int:
    """A monster's gold (the hero's own reading, core.invent.money_cnt,
    is the same sum over the COIN items of a pack)."""
    return sum(it.quan for it in mon.inventory if it.oclass == int(ObjClass.COIN))


# ------------------------------------------------------------
# the table (core.shknam_data)
# ------------------------------------------------------------


def test_the_shop_type_table_is_the_c_one():
    """Twelve rows; the eleven rolled ones total 100 %; the last row is
    the "unique" lighting store and must stay at 0 (C's comment); every
    iprobs row totals 100 %."""
    assert len(SHOPTYPES) == 12
    assert UNIQUE_SHOP_START == 11
    assert sum(t.prob for t in SHOPTYPES) == 100
    assert [t.prob for t in SHOPTYPES[UNIQUE_SHOP_START:]] == [0]
    assert SHOPTYPES[UNIQUE_SHOP_START].name2 == "lighting shop"
    assert sum(t.prob for t in SHOPTYPES[:UNIQUE_SHOP_START]) == 100
    for t in SHOPTYPES:
        assert sum(p for p, _ in t.iprobs) == 100, t.name
        assert len(t.iprobs) == 9  # C: the nine-slot struct itp array
        assert t.shknms, t.name


def test_the_shop_indices_run_in_room_type_order():
    """``shtypes[i]`` <-> ``SHOPBASE + i``: the room-type enum's order is
    the table's, which is why mkshop can add the index."""
    assert SHOPTYPES[0].name == "general store"
    assert SHOPTYPES[FODDER_SHOP].name2 == "vegetarian food shop"
    assert int(RoomType.SHOPBASE) + FODDER_SHOP == int(RoomType.FODDERSHOP)
    for i, t in enumerate(SHOPTYPES):
        assert RoomType(int(RoomType.SHOPBASE) + i) is not None, t.name
        assert 0 <= int(t.symb) < 18, t.name  # an object class, or RANDOM


def test_no_shopkeeper_name_is_repeated_within_a_list():
    for t in SHOPTYPES:
        assert len(set(t.shknms)) == len(t.shknms), t.name


# ------------------------------------------------------------
# mkshop -- the room pick and the type roll
# ------------------------------------------------------------


def test_mkshop_claims_the_first_eligible_room():
    """C's walk: an ordinary room, no staircase, exactly one door.  The
    two-door room and the staircase room are passed over; the third is
    claimed with rtype >= SHOPBASE and FILL_NORMAL, and nothing is
    created yet (C moved the stocking to the end of makelevel)."""
    m = blank_map(W, H)
    two_door = add_room(m, 3, 3, 8, 8, True, RoomType.OROOM, False)
    topologize(m, two_door)
    add_door(m, 3, 2, two_door)
    add_door(m, 9, 5, two_door)
    stairs_room = add_room(m, 12, 3, 18, 8, True, RoomType.OROOM, False)
    topologize(m, stairs_room)
    add_door(m, 12, 2, stairs_room)
    shop_room = add_room(m, 22, 3, 28, 8, True, RoomType.OROOM, False)
    topologize(m, shop_room)
    add_door(m, 22, 2, shop_room)
    stairs = [Stairway(pos=(15, 5), up=False)]

    w = _world(m)
    claimed = mkroom.mkshop(m, stairs, _rng())
    assert claimed is shop_room
    assert shop_room.rtype >= RoomType.SHOPBASE
    assert shop_room.needfill == FILL_NORMAL
    assert not [a for a in w.actors.values() if a.isshk]
    assert not _floor_items(w, 1)


def test_mkshop_refuses_a_room_the_stairs_are_in():
    """C: `has_dnstairs(sroom) || has_upstairs(sroom)` disqualifies the
    room outright -- both directions, unlike pick_room's rn2(3)."""
    m, room = _room_map()
    assert mkroom.mkshop(m, [Stairway(pos=(7, 6), up=False)], _rng()) is None
    assert mkroom.mkshop(m, [Stairway(pos=(7, 6), up=True)], _rng()) is None
    assert mkroom.mkshop(m, [], _rng()) is room


def test_mkshop_lights_the_room():
    """C: a dark shop is lit over its whole rectangle (walls included)
    before the type is rolled -- a shop you cannot see would be a shop
    you cannot shop in."""
    m, room = _room_map(lit=False)
    assert room.rlit is False
    assert mkroom.mkshop(m, [], _rng()) is room
    assert room.rlit is True
    for x in range(room.lx - 1, room.hx + 2):
        for y in range(room.ly - 1, room.hy + 2):
            assert m.tile_at((x, y)).lit is True, (x, y)


def test_mkshop_rolls_the_type_from_the_table():
    """The C walk: `j = rnd(100); while (j -= shtypes[i].prob) > 0: i++`
    -- 1..42 general store, 43..56 armor, ... 99..100 the health food
    store (the overshoot lands on the general store)."""
    cases = {
        1: RoomType.SHOPBASE,
        42: RoomType.SHOPBASE,
        43: RoomType.ARMORSHOP,
        56: RoomType.ARMORSHOP,
        57: RoomType.SCROLLSHOP,
        99: RoomType.FODDERSHOP,
        100: RoomType.FODDERSHOP,
    }
    for roll, expected in cases.items():
        m, room = _room_map()
        assert mkroom.mkshop(m, [], _FixedRng(roll)) is room
        assert room.rtype == expected, roll


def test_a_big_room_cannot_be_a_wand_or_book_shop():
    """C: `if (isbig(sroom) && (symb == WAND_CLASS ||
    symb == SPBOOK_CLASS)) i = 0` -- the big 10x7 room becomes a general
    store where the small one keeps the wand shop."""
    big, big_room = _room_map()  # 10x7 = 70 squares: big
    assert mkroom.isbig(big_room)
    mkroom.mkshop(big, [], _FixedRng(90))  # 90..92 is the wand shop
    assert big_room.rtype == RoomType.SHOPBASE

    small, small_room = _room_map(box=(5, 4, 8, 7))  # 4x4 = 16: small
    assert not mkroom.isbig(small_room)
    mkroom.mkshop(small, [], _FixedRng(90))
    assert small_room.rtype == RoomType.WANDSHOP


# ------------------------------------------------------------
# stock_room -- the shopkeeper
# ------------------------------------------------------------


def test_the_keeper_stands_just_inside_the_door():
    """C: good_shopdoor -- the door square moved one square into the
    room (the door is in the top wall, so the keeper stands one row
    below it)."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _rng())
    assert shk.good_shopdoor(m, room) == (0, (LX, LY))
    shk.stock_room(w, _rng(), m, room, 1)
    keeper = _kid(w, room)
    assert keeper.pos == (LX, LY)
    assert keeper.isshk and keeper.mpeaceful
    assert keeper.mdata is MONS[PM_SHOPKEEPER]


def test_the_eshk_extra_and_the_room_resident_are_filled():
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _rng())
    shk.stock_room(w, _rng(), m, room, 1)
    keeper = _kid(w, room)
    eshk = keeper.eshk
    assert eshk is not None
    assert eshk.parentmid == keeper.id
    assert eshk.shoproom == m.room_of(room)
    assert eshk.shoptype == int(room.rtype)
    assert eshk.shd == DOOR
    assert eshk.shk == keeper.pos
    assert eshk.shoplevel == 1
    assert eshk.shknam  # named from the shop type's list
    # the account is untouched in 4a (the bill is phase 4b)
    assert (eshk.debit, eshk.credit, eshk.robbed) == (0, 0, 0)
    assert room.resident == keeper.id
    # shop_keeper answers the same monster from the room number
    assert shk.shop_keeper(w, 1, m.room_of(room)) is keeper
    assert shk.shop_keeper(w, 2, m.room_of(room)) is None


def test_the_keeper_starts_with_its_capital():
    """C: mkmonmoney(shk, 1000 + 30 * rnd(100)) -- a purse, not a
    counter (gold is a COIN item, PLAN-MKOBJ.md D)."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _rng())
    shk.stock_room(w, _rng(), m, room, 1)
    keeper = _kid(w, room)
    assert 1030 <= _purse(keeper) <= 4000
    coins = [it for it in keeper.inventory if it.oclass == int(ObjClass.COIN)]
    assert len(coins) == 1  # one pile, never two


def test_the_jeweller_gets_a_touchstone_and_a_charging_scroll():
    """C: `if (shp->shknms == shkrings) mongets(TOUCHSTONE)`, and the
    rings / tools / wands lists get a scroll of charging."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(88))  # 87..89 is the ring shop
    assert room.rtype == RoomType.RINGSHOP
    shk.stock_room(w, _rng(), m, room, 1)
    otypes = {it.otyp for it in _kid(w, room).inventory}
    assert int(O.TOUCHSTONE) in otypes
    assert int(O.SCR_CHARGING) in otypes


def test_two_shops_on_a_level_never_share_a_name():
    """C: nameshk's "is name already in use on this level?" walk --
    every shopkeeper on a level gets its own name."""
    m = blank_map(W, H)
    first = add_room(m, 3, 3, 8, 8, True, RoomType.OROOM, False)
    topologize(m, first)
    add_door(m, 3, 2, first)
    second = add_room(m, 12, 3, 18, 8, True, RoomType.OROOM, False)
    topologize(m, second)
    add_door(m, 12, 2, second)

    w = _world(m)
    assert mkroom.mkshop(m, [], _rng(3)) is first
    shk.stock_room(w, _rng(3), m, first, 1)
    assert mkroom.mkshop(m, [], _rng(4)) is second
    shk.stock_room(w, _rng(4), m, second, 1)
    names = {mon.eshk.shknam for mon in _mons(w, 1) if mon.isshk}
    assert len(names) == 2
    assert_item_locations(w)


def test_the_name_comes_from_the_shop_types_list():
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(43))  # the armor shop
    assert room.rtype == RoomType.ARMORSHOP
    shk.stock_room(w, _rng(), m, room, 1)
    name = _kid(w, room).eshk.shknam
    bare = name[1:] if name[0] in "-_+|=" else name
    assert bare in SHKARMORS


def test_the_name_follows_the_seed():
    """The C seed is `m_id + ledger_no - (nseed % 13) + (nseed % 5)`;
    pyhack reads the level for the ledger, so two levels give two
    names."""
    names = set()
    for lev in (1, 2, 3, 4):
        m, room = _room_map()
        w = _world(m, lev)
        mkroom.mkshop(m, [], _rng())
        shk.stock_room(w, _rng(), m, room, lev)
        names.add(_kid(w, room).eshk.shknam)
    assert len(names) >= 2


# ------------------------------------------------------------
# stock_room -- the doorway fix-up
# ------------------------------------------------------------


def test_a_doorway_without_a_door_is_opened():
    m, room = _room_map(mask=DoorMask(0))
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(1))
    shk.stock_room(w, _rng(), m, room, 1)
    tile = m.tile_at(DOOR)
    assert tile.typ == TerrainType.DOOR
    assert tile.door_mask == DoorMask.ISOPEN
    assert tile.engr is None  # an open door carries no sign


def test_a_secret_door_becomes_a_real_one():
    """C: cvt_sdoor_to_door -- the shop doorway is never secret."""
    m, room = _room_map(typ=TerrainType.SDOOR, mask=DoorMask(0))
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(1))
    shk.stock_room(w, _rng(), m, room, 1)
    tile = m.tile_at(DOOR)
    assert tile.typ == TerrainType.DOOR
    assert tile.door_mask == DoorMask.CLOSED


def test_a_trapped_door_is_locked_and_signed():
    """C: a trapped shop door loses the trap and locks; a locked door
    gets "Closed for inventory" engraved on the square *opposite* the
    shop's inside (the corridor side -- the sign is for the street)."""
    m, room = _room_map(mask=DoorMask.CLOSED | DoorMask.TRAPPED)
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(1))
    shk.stock_room(w, _rng(), m, room, 1)
    assert m.tile_at(DOOR).door_mask == DoorMask.LOCKED
    sign = m.tile_at((LX, LY - 2))  # one row outside the locked door
    assert sign.engr is not None
    assert sign.engr.text == "Closed for inventory"
    # C coerces the square to floor terrain when it is neither ROOM
    # nor CORR (`*in_rooms(m, n, 0) ? ROOM : CORR`)
    assert sign.typ in (TerrainType.CORR, TerrainType.ROOM)


def test_the_locked_door_sign_is_on_the_corridor_side():
    """inside_shop() tells the shop side from the corridor side, and C
    steps the engraving *away* from the shop (the sign hangs in the
    corridor, where a customer can read it)."""
    m, room = _room_map(mask=DoorMask.LOCKED)
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(1))
    shk.stock_room(w, _rng(), m, room, 1)
    assert m.tile_at((LX, LY)).engr is None  # the shop floor is clear
    assert m.tile_at((LX, LY - 2)).engr is not None


def test_inside_shop_answers_a_room_number():
    m, room = _room_map()
    mkroom.mkshop(m, [], _FixedRng(1))
    assert shk.inside_shop(m, (LX, LY)) == m.room_of(room)
    # outside the room
    assert shk.inside_shop(m, (0, 0)) == NO_ROOM
    # the door itself is a boundary (edge) square of the room
    assert shk.inside_shop(m, DOOR) == NO_ROOM
    # an ordinary room is not a shop
    other = add_room(m, 22, 3, 28, 8, True, RoomType.OROOM, False)
    topologize(m, other)
    assert shk.inside_shop(m, (24, 5)) == NO_ROOM


# ------------------------------------------------------------
# stock_room -- the stock
# ------------------------------------------------------------


def test_every_free_square_gets_an_object_but_the_door_row():
    """C: `for (sx = lx; sx <= hx; sx++) for (sy = ly; ...)` over
    stock_room_goodpos -- everything but the row the door stands on.
    The shopkeeper's own square is stocked too; a mimic (rare at depth
    1) takes a square instead of an object."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _rng())
    shk.stock_room(w, _rng(), m, room, 1)

    on_items = {it.pos for it in _floor_items(w, 1)}
    occupied = on_items | {mon.pos for mon in _mons(w, 1)}
    stocked = set()
    for x in range(room.lx, room.hx + 1):
        for y in range(room.ly, room.hy + 1):
            if y == room.ly:  # the door row (the door is directly above)
                assert (x, y) not in on_items
                continue
            stocked.add((x, y))
    assert len(stocked) == STOCKED
    for pos in stocked:
        assert pos in occupied, pos
    assert m.flags.has_shop is True
    assert_item_locations(w)


def test_the_stock_matches_the_shop_class():
    """An armor dealership stocks armor (and the 10 % of weapons its
    iprobs row allows) -- never food."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(43))  # the armor shop
    shk.stock_room(w, _rng(2), m, room, 1)
    classes = {it.oclass for it in _floor_items(w, 1)}
    assert classes <= {int(ObjClass.ARMOR), int(ObjClass.WEAPON)}
    assert int(ObjClass.ARMOR) in classes


def test_the_general_store_stocks_anything():
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(1))  # the general store
    shk.stock_room(w, _rng(5), m, room, 1)
    classes = {it.oclass for it in _floor_items(w, 1)}
    assert len(classes) > 1  # RANDOM_CLASS rolls per square


def test_get_shop_item_rolls_the_class_or_a_specific_type():
    """C: a negative itype is a specific object, a positive one a
    class, and VEGETARIAN_CLASS the health-food pseudo-class."""
    deli = 5  # "delicatessen": 83 food, then the named potions / box
    assert shk.get_shop_item(_FixedRng(1), deli) == int(ObjClass.FOOD)
    assert shk.get_shop_item(_FixedRng(84), deli) == -int(O.POT_FRUIT_JUICE)
    assert shk.get_shop_item(_FixedRng(100), deli) == -int(O.ICE_BOX)
    # the health food store: 1..70 is the vegetarian pseudo-class
    assert shk.get_shop_item(_FixedRng(1), FODDER_SHOP) == VEGETARIAN_CLASS
    assert shk.get_shop_item(_FixedRng(71), FODDER_SHOP) == (-int(O.POT_FRUIT_JUICE))


def test_the_health_food_store_stocks_its_pseudo_class():
    """The VEGETARIAN_CLASS roll is shkveg: a vegetarian FOOD_CLASS row,
    never a corpse or a tin of meat."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _FixedRng(100))  # the health food store
    assert room.rtype == RoomType.FODDERSHOP
    shk.stock_room(w, _rng(2), m, room, 1)
    foods = [it for it in _floor_items(w, 1) if it.oclass == int(ObjClass.FOOD)]
    assert foods
    for it in foods:
        # the type, not the object: a tin's variety (C: HEALTHY_TIN)
        # is not ported, so an object-level check would reject it
        assert shk.veggy_item(None, it.otyp), it.name


def test_veggy_item_and_shkveg():
    """The type-only call judges a tin / corpse by its corpsenm, which C
    seeds with PM_LICHEN; shkveg rolls a vegetarian FOOD_CLASS row."""
    assert shk.veggy_item(None, int(O.APPLE)) is True
    assert shk.veggy_item(None, int(O.EGG)) is True
    assert shk.veggy_item(None, int(O.TIN)) is True  # the lichen standin
    assert shk.veggy_item(None, int(O.CORPSE)) is True
    assert shk.veggy_item(None, int(O.SHORT_SWORD)) is False
    for seed in range(5):
        otyp = shk.shkveg(_rng(seed))
        assert shk.veggy_item(None, otyp) is True


def test_a_mimic_may_take_a_square():
    """C: `rn2(100) < depth && !MON_AT && mkclass(S_MIMIC) && makemon`
    -- at depth 1 that is one square in a hundred; deeper it happens."""
    found = False
    for lev in (5, 8):
        for seed in range(6):
            m, room = _room_map()
            w = _world(m, lev)
            mkroom.mkshop(m, [], _rng(seed))
            shk.stock_room(w, _rng(seed), m, room, lev)
            on_items = {it.pos for it in _floor_items(w, lev)}
            for mon in _mons(w, lev):
                if mon.mdata is not None and mon.mdata.mlet == S_MIMIC:
                    found = True
                    assert mon.pos not in on_items  # a monster, not both
    assert found, "no mimic in twelve stocked shops"


# ------------------------------------------------------------
# the refusals and the room shape
# ------------------------------------------------------------


def test_no_eligible_room_means_no_shop():
    """C's walk answers NULL when no room qualifies."""
    m = blank_map(W, H)
    assert mkroom.mkshop(m, [], _rng()) is None
    two_door = add_room(m, 3, 3, 8, 8, True, RoomType.OROOM, False)
    topologize(m, two_door)
    add_door(m, 3, 2, two_door)
    add_door(m, 9, 5, two_door)
    assert mkroom.mkshop(m, [], _rng()) is None


def test_a_room_without_a_door_gets_no_keeper():
    """C: shkinit's good_shopdoor answers -1 and stock_room gives up --
    no keeper, no stock, no exception.  mkshop never claims a doorless
    room (it wants exactly one door), so this is the special-level
    shape: a shop rtype set from outside."""
    m, room = _room_map(door=False)
    room.rtype = RoomType.ARMORSHOP
    room.needfill = FILL_NORMAL
    w = _world(m)
    shk.stock_room(w, _rng(), m, room, 1)
    assert shk.good_shopdoor(m, room) is None
    assert not [a for a in w.actors.values() if a.isshk]
    assert not _floor_items(w, 1)


def test_the_stocked_room_stays_walkable():
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _rng())
    shk.stock_room(w, _rng(), m, room, 1)
    for x in range(room.lx, room.hx + 1):
        for y in range(room.ly, room.hy + 1):
            assert m.is_walkable((x, y)), (x, y)


def test_stock_goodpos_rejects_the_door_row_and_the_walls():
    m, room = _room_map()
    mkroom.mkshop(m, [], _FixedRng(1))
    rmno = m.room_of(room)
    assert not shk.stock_goodpos(m, room, rmno, DOOR, (LX, LY))
    assert shk.stock_goodpos(m, room, rmno, DOOR, (LX, LY + 1))
    # a wall square is not a floor square (C: IS_ROOM)
    assert not shk.stock_goodpos(m, room, rmno, (0, 0), (LX - 1, LY))
    # an irregular room also keeps the ring around the door clear
    m2 = blank_map(W, H)
    room2 = add_room(m2, LX, LY, HX, HY, True, RoomType.OROOM, False)
    topologize(m2, room2)
    room2.irregular = True
    rmno2 = m2.room_of(room2)
    assert not shk.stock_goodpos(m2, room2, rmno2, DOOR, (LX, LY))
    assert shk.stock_goodpos(m2, room2, rmno2, DOOR, (LX + 2, LY + 2))


def test_the_shop_room_is_found_by_search_special():
    m, room = _room_map()
    mkroom.mkshop(m, [], _rng())
    assert mkroom.search_special(m, ANY_SHOP) is room


# ------------------------------------------------------------
# the whole pipeline (makelevel with specials)
# ------------------------------------------------------------


def test_a_generated_level_can_hold_a_stocked_shop():
    """do_mkroom(SHOPBASE) -> mkshop, then the end-of-level loop ->
    stock_room: the integration the phase exists for.  No exception, a
    shop somewhere, its keeper at home.

    The shop roll wants ``depth > 1`` and ``depth < max_lev - 5``
    (C's medusa cap, faked -- PLAN-SPECIAL-ROOMS.md decision 10), so
    the test builds a deep level of a deep dungeon.
    """
    shop_found = None
    for seed in range(40):
        w = World(map=blank_map(80, 21))
        w.max_lev = 20
        m = makelevel(w, w.map, _rng(seed), 10, specials=True)
        shop = mkroom.search_special(m, ANY_SHOP)
        if shop is not None:
            shop_found = (w, m, shop)
            break
    assert shop_found is not None, "no seed made a shop"
    w, m, shop = shop_found
    keeper = shk.room_keeper(w, shop)
    assert keeper is not None and keeper.isshk
    assert m.flags.has_shop is True
    assert distmin(keeper.pos, shop.doors[0]) <= 1
    assert_item_locations(w)


# ============================================================
# phase 4b -- prices, the bill, the Pay
# ============================================================

# the first real wand otyp (the WAND class base is the generic
# placeholder; +1 is the "light" wand)
WAND_OTYP = BASES[int(ObjClass.WAND)] + 1


def _item(otyp: int, **kw) -> Item:
    """A hand-built fine-grained object (the test's mksobj stand-in).
    The extra kwargs (spe, dknown, quan, oeaten, ...) are set after
    construction."""
    row = OBJECTS[otyp]
    name = row.name if row.name is not None else "obj"
    item_id = kw.pop("id", f"t{otyp}")
    item = Item(
        id=item_id,
        otype=coarse_otype(otyp),
        name=name,
        otyp=otyp,
        oclass=int(row.oclass),
    )
    for k, v in kw.items():
        setattr(item, k, v)
    return item


def _price_world() -> World:
    w = World(map=blank_map(W, H))
    w.actors["player"] = make_hero(pos=(1, 1))
    return w


def _find_cost(cost: int) -> int:
    for i in range(NUM_OBJECTS):
        row = OBJECTS[i]
        if not row.unique and row.cost == cost:
            return i
    raise AssertionError(f"no non-unique otyp with cost {cost}")


def _msgs(events) -> List[str]:
    return [e.text for e in events if isinstance(e, MessageEvent)]


# ------------------------------------------------------------
# getprice -- the base price (the table-driven core of 4b)
# ------------------------------------------------------------


def test_getprice_weapon_and_armor_enchant():
    """The ARMOR / WEAPON branch: an enchant bonus (spe > 0) adds
    10 * spe to the base cost; spe 0 / negative is the base."""
    w = _price_world()
    sword = _item(int(O.SHORT_SWORD))
    base = OBJECTS[int(O.SHORT_SWORD)].cost
    assert base > 0
    assert shk.getprice(w, sword, False) == base
    sword.spe = 2
    assert shk.getprice(w, sword, False) == base + 20
    sword.spe = -1  # a cursed bonus adds nothing (C: spe > 0)
    assert shk.getprice(w, sword, False) == base

    armor_otyp = _find_armor_cost(base)
    armor = _item(armor_otyp)
    abase = OBJECTS[armor_otyp].cost
    assert shk.getprice(w, armor, False) == abase
    armor.spe = 1
    assert shk.getprice(w, armor, False) == abase + 10


def _find_armor_cost(any_base: int) -> int:
    for i in range(NUM_OBJECTS):
        row = OBJECTS[i]
        if not row.unique and int(row.oclass) == int(ObjClass.ARMOR) and row.cost > 0:
            return i
    raise AssertionError("no armor row")


def test_getprice_water_free_healing_priced():
    """The POTION branch: plain water (neither blessed nor cursed) is
    worth 0; a healing potion is its base cost; a blessed water is
    priced (the BUC half of the zero-case)."""
    w = _price_world()
    assert shk.getprice(w, _item(int(O.POT_WATER)), False) == 0
    blessed = _item(int(O.POT_WATER), blessed=True)
    assert shk.getprice(w, blessed, False) == OBJECTS[int(O.POT_WATER)].cost
    healing = _item(int(O.POT_HEALING))
    assert shk.getprice(w, healing, False) == OBJECTS[int(O.POT_HEALING)].cost


def test_getprice_cancelled_wand_free_charged_priced():
    """The WAND branch: a cancelled / empty wand (spe == -1) is worth
    0; a charged wand is its base cost."""
    w = _price_world()
    assert shk.getprice(w, _item(WAND_OTYP, spe=-1), False) == 0
    charged = _item(WAND_OTYP, spe=5)
    assert shk.getprice(w, charged, False) == OBJECTS[WAND_OTYP].cost
    # a used-up (but not cancelled) wand, spe == 0, keeps its base price
    empty = _item(WAND_OTYP, spe=0)
    assert shk.getprice(w, empty, False) == OBJECTS[WAND_OTYP].cost


def test_getprice_food_oeaten_is_free():
    """The FOOD branch: a full piece is its base cost (the hero is not
    hungry, so no multiplier); a partly-eaten piece (oeaten) is 0."""
    w = _price_world()
    apple = _item(int(O.APPLE))
    base = OBJECTS[int(O.APPLE)].cost
    assert shk.getprice(w, apple, False) == base
    apple.oeaten = 1
    assert shk.getprice(w, apple, False) == 0


def test_getprice_candle_age_boundary():
    """The TOOL branch: a candle younger than 20 * its cost is half
    price; at / past the boundary it is full price."""
    w = _price_world()
    candle = _item(int(O.TALLOW_CANDLE))
    base = OBJECTS[int(O.TALLOW_CANDLE)].cost
    assert base > 0
    candle.age = 0
    assert shk.getprice(w, candle, False) == base // 2
    candle.age = 20 * base - 1
    assert shk.getprice(w, candle, False) == base // 2
    candle.age = 20 * base
    assert shk.getprice(w, candle, False) == base
    # a non-candle tool is never halved
    other = _item(_find_tool_cost())
    assert shk.getprice(w, other, False) == OBJECTS[other.otyp].cost


def _find_tool_cost() -> int:
    for i in range(NUM_OBJECTS):
        row = OBJECTS[i]
        if (
            not row.unique
            and int(row.oclass) == int(ObjClass.TOOL)
            and row.cost > 0
            and i not in (int(O.TALLOW_CANDLE), int(O.WAX_CANDLE))
        ):
            return i
    raise AssertionError("no tool row")


def test_getprice_hunger_multiplier_hit_by_uhs():
    """The FOOD hunger multiplier: for a BOLD food (shk_buying False) at
    uhs 2..6 the price is base * uhs; selling (shk_buying True) takes no
    multiplier (C: `u.uhs >= HUNGRY && !shk_buying`)."""
    w = _price_world()
    apple = _item(int(O.APPLE))
    base = OBJECTS[int(O.APPLE)].cost
    for uhs_val in (2, 3, 4, 5, 6):
        w.hero.uhs = HungerState(uhs_val)
        assert shk.getprice(w, apple, False) == base * uhs_val
        assert shk.getprice(w, apple, True) == base
    # below HUNGRY (uhs 0..1) there is no multiplier at all
    for uhs_val in (0, 1):
        w.hero.uhs = HungerState(uhs_val)
        assert shk.getprice(w, apple, False) == base


# ------------------------------------------------------------
# get_cost -- the price that goes on the bill
# ------------------------------------------------------------


def test_get_cost_zero_floor():
    """The 0->5 floor: a known plain-water potion (getprice 0) is billed
    5.  The type's name must be known too, or the un-ID'd surcharge
    (x4/3) moves the floor from 5 to 7."""
    w = _price_world()
    w.obj_tables.name_known.add(int(O.POT_WATER))
    water = _item(int(O.POT_WATER), dknown=True)
    assert shk.get_cost(w, water, None) == 5


def test_get_cost_unknown_surcharge():
    """The un-ID'd surcharge: an unknown item is billed x4/3 (C's
    round-half-up), a known item its base.  The dknown-vs-unknown pair
    is the plan's (x4/3) check."""
    w = _price_world()
    otyp = int(O.POT_HEALING)
    c = OBJECTS[otyp].cost
    unknown = _item(otyp, dknown=False)
    expected = ((c * 4 * 10) // 3 + 5) // 10
    assert expected != c  # the surcharge actually moved the price
    assert shk.get_cost(w, unknown, None) == expected
    w.obj_tables.name_known.add(otyp)
    known = _item(otyp, dknown=True)
    assert shk.get_cost(w, known, None) == c


def test_get_cost_round_half_up_disagrees_with_floor():
    """C's `((tmp*10)/div + 5)/10` rounds half up; a plain floor
    division disagrees at the .5-and-over cases.  Find a base cost where
    the two differ and pin C's answer."""
    w = _price_world()
    found = None
    for i in range(NUM_OBJECTS):
        row = OBJECTS[i]
        if row.unique or row.cost == 0:
            continue
        c_round = ((row.cost * 4 * 10) // 3 + 5) // 10
        c_floor = (row.cost * 4) // 3
        if c_round != c_floor:
            found = (i, c_round)
            break
    assert found is not None, "no cost where the round-half-up differs"
    otyp, c_round = found
    unknown = _item(otyp, dknown=False)
    assert shk.get_cost(w, unknown, None) == c_round


def test_get_cost_anger_surcharge():
    """The anger surcharge (4c sets eshk.surcharge): a known item takes
    (tmp + 2) // 3 on top of its price."""
    w = _price_world()
    otyp = int(O.POT_HEALING)
    w.obj_tables.name_known.add(otyp)
    item = _item(otyp, dknown=True)
    base = OBJECTS[otyp].cost
    assert shk.get_cost(w, item, None) == base
    keeper = make_monster(kind="goblin", pos=(1, 1))
    keeper.isshk = True
    keeper.eshk = Eshk()
    keeper.eshk.surcharge = True
    assert shk.get_cost(w, item, keeper) == base + (base + 2) // 3


# ------------------------------------------------------------
# the bill -- pickup in a shop bills the item
# ------------------------------------------------------------


def _stocked_shop():
    """A claimed + stocked shop (the 4a helpers), with the keeper."""
    m, room = _room_map()
    w = _world(m)
    mkroom.mkshop(m, [], _rng())
    shk.stock_room(w, _rng(), m, room, 1)
    keeper = _kid(w, room)
    return m, room, w, keeper


def test_pickup_in_shop_bills_the_item():
    """The pickup hook: taking a stocked item inside the shop puts it on
    the bill (price == get_cost, item.unpaid, the debt is price * quan).
    No extra message -- C's pickup line is the only one."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    assert eshk is not None
    # a stocked square that is not the keeper's own
    stocked = None
    for it in _floor_items(w, 1):
        if it.pos != eshk.shk:
            stocked = it
            break
    assert stocked is not None
    w.hero.pos = stocked.pos
    from core.pickup import pickup

    events = pickup(w, "player", _rng())
    # exactly the one pickup message (the billing is silent)
    assert _msgs(events) == [f"You pick up the {stocked.name}."]
    entry = eshk.bill.get(stocked.id)
    assert entry is not None
    assert entry.price == shk.get_cost(w, stocked, keeper)
    assert entry.bquan == stocked.quan
    assert stocked.unpaid is True
    assert eshk.billct == 1
    assert shk.shop_debt(eshk) == entry.price * entry.bquan
    assert onbill_check(eshk, stocked)
    assert_item_locations(w)


def onbill_check(eshk, item):
    return shk.onbill(item, eshk) is not None


def test_second_item_is_a_second_entry():
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    items = [it for it in _floor_items(w, 1) if it.pos != eshk.shk][:2]
    assert len(items) == 2
    from core.pickup import pickup

    for it in items:
        w.hero.pos = it.pos
        pickup(w, "player", _rng())
    assert len(eshk.bill) == 2
    assert eshk.billct == 2
    for it in items:
        assert it.unpaid is True
    assert shk.shop_debt(eshk) == sum(e.price * e.bquan for e in eshk.bill.values())
    assert_item_locations(w)


def test_no_charge_item_is_not_billed():
    """The hero's own gear (no_charge) picked up inside the shop is not
    billed."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    spot = (room.lx + 1, room.ly)  # the empty door row, not the keeper's
    item = _item(int(O.APPLE))
    place_object(w, item, spot, 1)
    item.no_charge = True
    w.hero.pos = spot
    from core.pickup import pickup

    pickup(w, "player", _rng())
    assert item.id not in eshk.bill
    assert item.unpaid is False
    assert money_cnt(w.hero) == 0
    assert_item_locations(w)


def test_coin_is_never_billed():
    """Gold picked up in a shop is not billed (C: the COIN_CLASS skip)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    spot = (room.lx + 1, room.ly)
    gold = _item(int(O.GOLD_PIECE), quan=50)
    place_object(w, gold, spot, 1)
    w.hero.pos = spot
    from core.pickup import pickup

    pickup(w, "player", _rng())
    assert gold.id not in eshk.bill
    assert money_cnt(w.hero) == 50
    assert_item_locations(w)


def test_the_keeper_s_own_square_is_not_a_costly_spot():
    """costly_spot excludes the keeper's square (a keeper stocking its
    own counter is not a sale)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    assert shk.costly_spot(w, *eshk.shk) is False
    # a neighbouring shop square IS costly
    assert shk.costly_spot(w, room.lx + 1, room.ly + 1) is True
    # outside the shop it is not
    assert shk.costly_spot(w, 0, 0) is False


def test_bill_full_gives_the_item_free():
    """BILLSZ: a bill with 200 entries makes the 201st pickup free
    ("You got that for free!"), with no entry added."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    for i in range(shk.BILLSZ):
        eshk.bill[f"fake{i}"] = BillEntry(price=1, bquan=1, name="x")
    eshk.billct = len(eshk.bill)
    assert eshk.billct == shk.BILLSZ
    item = _item(int(O.APPLE), dknown=True, id="free1")
    w.obj_tables.name_known.add(int(O.APPLE))
    events = shk.add_one_tobill(w, keeper, item)
    assert "You got that for free!" in _msgs(events)
    assert item.id not in eshk.bill
    assert item.unpaid is False


# ------------------------------------------------------------
# the entry / leave hook -- in_shop and the no_charge marks
# ------------------------------------------------------------


def test_entering_the_shop_marks_carried_gear_no_charge():
    m, room, w, keeper = _stocked_shop()
    gear = _item(int(O.SHORT_SWORD), id="gear")
    addinv(w, "player", gear)
    w.hero.pos = (1, 1)
    assert w.hero.in_shop == NO_ROOM
    assert gear.no_charge is False
    # step inside
    inside = (room.lx + 1, room.ly + 1)
    shk.track_shop(w, inside)
    assert w.hero.in_shop == m.room_of(room)
    assert gear.no_charge is True
    # a coin is never marked
    gold = _item(int(O.GOLD_PIECE), quan=10, id="g")
    addinv(w, "player", gold)
    shk.track_shop(w, (1, 1))  # leave
    shk.track_shop(w, inside)  # re-enter
    assert gold.no_charge is False
    assert gear.no_charge is True
    # step out again: the marks are cleared (unpaid stays)
    shk.track_shop(w, (1, 1))
    assert w.hero.in_shop == NO_ROOM
    assert gear.no_charge is False


# ------------------------------------------------------------
# the Pay command (p -> do_pay, pay-all)
# ------------------------------------------------------------


def _billed_shop():
    """A stocked shop with two KNOWN items billed and the hero in it."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    it1 = _item(int(O.APPLE), dknown=True, id="b1")
    it2 = _item(int(O.POT_HEALING), dknown=True, id="b2")
    w.obj_tables.name_known.add(int(O.APPLE))
    w.obj_tables.name_known.add(int(O.POT_HEALING))
    # the hero carries them (as if picked up inside the shop), so they
    # are in world.items and do_pay can find them to clear the bill
    addinv(w, "player", it1)
    addinv(w, "player", it2)
    shk.add_one_tobill(w, keeper, it1)
    shk.add_one_tobill(w, keeper, it2)
    w.hero.pos = (room.lx + 1, room.ly + 1)
    return m, room, w, keeper, eshk, it1, it2


def test_do_pay_clears_the_bill_and_moves_the_gold():
    m, room, w, keeper, eshk, it1, it2 = _billed_shop()
    total = shk.shop_debt(eshk)
    assert total > 0
    keeper_before = _purse(keeper)
    addinv(w, "player", _item(int(O.GOLD_PIECE), quan=total + 100, id="g"))
    hero_before = money_cnt(w.hero)  # total + 100
    assert hero_before == total + 100
    events = step(w, PayCommand(), _rng())
    msgs = _msgs(events)
    bought = [x for x in msgs if x.startswith("You bought")]
    assert len(bought) == 2
    assert any("Thank you for shopping in" in x for x in msgs)
    # the bill is cleared and the items are paid
    assert eshk.billct == 0
    assert len(eshk.bill) == 0
    assert it1.unpaid is False and it2.unpaid is False
    # the plan's 4b model: buying establishes credit
    assert eshk.credit == total
    # the gold moved: the hero down by total, the keeper up by total
    assert money_cnt(w.hero) == hero_before - total
    assert _purse(keeper) == keeper_before + total
    assert_item_locations(w)


def test_do_pay_refuses_without_enough_gold():
    m, room, w, keeper, eshk, it1, it2 = _billed_shop()
    total = shk.shop_debt(eshk)
    assert total > 0
    addinv(w, "player", _item(int(O.GOLD_PIECE), quan=total - 1, id="g"))
    assert money_cnt(w.hero) == total - 1
    events = step(w, PayCommand(), _rng())
    # (the monster turns follow -- the keeper and a mimic are nearby --
    # but the refusal is the first message)
    assert any("enough gold to pay" in x for x in _msgs(events)), _msgs(events)
    # the bill and the wallet are untouched
    assert eshk.billct == 2
    assert money_cnt(w.hero) == total - 1
    assert it1.unpaid is True and it2.unpaid is True


def test_do_pay_with_no_debt_says_so():
    m, room, w, keeper = _stocked_shop()
    w.hero.pos = (room.lx + 1, room.ly + 1)
    events = step(w, PayCommand(), _rng())
    assert "You don't owe any gold here." in _msgs(events)


def test_do_pay_outside_a_shop_refuses():
    w = _world(blank_map(W, H))
    w.hero.pos = (1, 1)
    events = step(w, PayCommand(), _rng())
    assert "You are not in a shop." in _msgs(events)


def test_pay_debt_establishes_credit_on_a_clean_account():
    """The plan's 4b model: against a clean account (debit 0) the whole
    payment becomes credit -- buying establishes credit (the debit / loan
    branches are ported for 4c reuse)."""
    eshk = Eshk()  # debit 0, credit 0, loan 0
    shk.pay_debt(eshk, 100)
    assert eshk.credit == 100
    assert eshk.debit == 0
    # a second payment accumulates
    shk.pay_debt(eshk, 50)
    assert eshk.credit == 150
    # the debit branch (4c): a debt is paid off from the amount first
    eshk2 = Eshk()
    eshk2.debit = 30
    shk.pay_debt(eshk2, 10)
    assert eshk2.debit == 20
    assert eshk2.credit == 0


# ============================================================
# phase 4c -- the police (the robbery, the door block, the surcharge,
# the EF_PAY reprice, and the death-time inheritance)
# ============================================================


def _inside_shop_pos(room: Room) -> Pos:
    """A shop floor square that is not the door row and not the
    keeper's square (a place the hero can stand inside)."""
    return (room.lx + 1, room.ly + 1)


def _bill_item(w: World, keeper, item: Item) -> None:
    """Put `item` on the keeper's bill (the 4b add_one_tobill), carrying
    it as if just picked up."""
    from core.shk import add_one_tobill

    addinv(w, "player", item)
    add_one_tobill(w, keeper, item)


def test_stolen_value_is_the_bill_total():
    """stolen_value is the value the hero owes: the bill total (debit +
    price*bquan) -- C's per-item sum collapsed to the 4b model."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="sv1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    assert shk.stolen_value(w, keeper) == shk.shop_debt(eshk)
    assert shk.stolen_value(w, keeper) == eshk.bill[item.id].price * item.quan


def test_leaving_with_unpaid_goods_is_a_robbery():
    """The 4c police: leaving with an unsettled bill is a robbery -- the
    bill becomes eshk.robbed, the keeper turns hostile (rile_shk /
    hot_pursuit), and the messages come out."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.POT_HEALING), dknown=True, id="rob1")
    w.obj_tables.name_known.add(int(O.POT_HEALING))
    _bill_item(w, keeper, item)
    total = shk.shop_debt(eshk)
    assert total > 0
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    shk.track_shop(w, inside)  # enter: in_shop is set
    w.hero.pos = (1, 1)
    events = shk.track_shop(w, (1, 1))  # leave with the unpaid goods
    msgs = _msgs(events)
    assert any("escaped the shop without paying" in x for x in msgs)
    assert any("stole" in x and str(total) in x for x in msgs)
    assert eshk.robbed == total
    assert keeper.mpeaceful is False  # the keeper is hostile now
    assert eshk.following is True
    assert eshk.surcharge is True
    assert eshk.billct == 0  # the bill is settled
    assert len(eshk.bill) == 0
    assert item.unpaid is False  # no longer on a bill (stolen)
    assert w.hero.in_shop == NO_ROOM
    assert_item_locations(w)


def test_credit_covers_the_bill_on_leaving():
    """A credit that covers the bill pays it off: no robbery, the keeper
    stays peaceful, the credit is cleared (C: rob_shop's credit half)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="cred1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    total = shk.shop_debt(eshk)
    assert total > 0
    eshk.credit = total  # the hero has enough credit
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    shk.track_shop(w, inside)
    w.hero.pos = (1, 1)
    events = shk.track_shop(w, (1, 1))  # leave
    msgs = _msgs(events)
    assert any("credit" in x and "cover" in x for x in msgs)
    assert eshk.robbed == 0
    assert keeper.mpeaceful is True  # stays peaceful
    assert eshk.credit == 0  # cleared by setpaid
    assert eshk.billct == 0
    assert_item_locations(w)


def test_rile_shk_marks_up_the_bill_and_angers():
    """rile_shk makes the keeper angry (mpeaceful False) and, once, sets
    the surcharge, marking up every bill entry by (price + 2) // 3."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="rile1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    old_price = eshk.bill[item.id].price
    assert keeper.mpeaceful is True
    assert eshk.surcharge is False
    shk.rile_shk(keeper)
    assert keeper.mpeaceful is False
    assert eshk.surcharge is True
    assert eshk.bill[item.id].price == old_price + (old_price + 2) // 3
    # a second rile does not mark up again (the surcharge is already set)
    price_after = eshk.bill[item.id].price
    shk.rile_shk(keeper)
    assert eshk.bill[item.id].price == price_after


def test_block_door_holds_the_keeper_at_the_door():
    """The keeper blocks the shop door while it is owed something and the
    hero is inside: the bare name in the message, the shop's own door."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="blk1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    w.hero.pos = _inside_shop_pos(room)
    w.hero.in_shop = m.room_of(room)  # the hero is in the shop
    door = eshk.shd
    block = shk.block_door(w, door[0], door[1])
    assert block is not None
    assert "blocks your way" in block.text
    bare = eshk.shknam[1:] if eshk.shknam[0] in "-_+|=" else eshk.shknam
    assert bare in block.text


def test_block_door_is_open_when_the_bill_is_settled():
    """No debt (no bill / debit / robbed): the way is open."""
    m, room, w, keeper = _stocked_shop()
    w.hero.pos = _inside_shop_pos(room)
    w.hero.in_shop = m.room_of(room)
    door = keeper.eshk.shd
    assert shk.block_door(w, door[0], door[1]) is None


def test_block_door_does_not_block_a_closed_shop():
    """A dead keeper (a closed shop) does not block the door."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="blk2")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    w.hero.pos = _inside_shop_pos(room)
    w.hero.in_shop = m.room_of(room)
    door = eshk.shd
    keeper.alive = False
    assert shk.block_door(w, door[0], door[1]) is None


def test_the_keeper_blocks_the_door_in_step():
    """Integration: a hero inside the shop, diagonally adjacent to the
    door, cannot move onto it while a bill is unsettled (core.step's
    block_door hook refuses the move)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="blk3")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    door = eshk.shd
    spot = (door[0] + 1, door[1] + 1)  # one square in from the door
    w.hero.pos = spot
    w.hero.in_shop = m.room_of(room)
    events = step(w, MoveCommand(dx=-1, dy=-1), _rng())
    msgs = _msgs(events)
    assert any("blocks your way" in x for x in msgs)
    assert w.hero.pos == spot  # the hero did not step onto the door


def test_alter_cost_reprices_a_billed_item():
    """alter_cost: an item whose cost rises on the bill (an enchantment)
    is repriced up to get_cost."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    sword = _item(int(O.SHORT_SWORD), dknown=True, id="ac1", spe=0)
    w.obj_tables.name_known.add(int(O.SHORT_SWORD))
    _bill_item(w, keeper, sword)
    base_price = eshk.bill[sword.id].price
    assert base_price == OBJECTS[int(O.SHORT_SWORD)].cost  # spe 0
    sword.spe = 2  # enchanted
    shk.alter_cost(w, sword, 0)
    assert eshk.bill[sword.id].price == base_price + 20


def test_alter_cost_does_not_decrease_the_bill():
    """A de-enchantment (a lower cost) never refunds the bill: the price
    only goes up (C: `if (new_price > bp->price || amt < 0)`)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    sword = _item(int(O.SHORT_SWORD), dknown=True, id="ac2", spe=2)
    w.obj_tables.name_known.add(int(O.SHORT_SWORD))
    _bill_item(w, keeper, sword)
    high_price = eshk.bill[sword.id].price  # base + 20
    sword.spe = 0  # de-enchanted
    shk.alter_cost(w, sword, 0)
    assert eshk.bill[sword.id].price == high_price


def test_alter_cost_is_a_no_op_off_the_bill():
    """An item that is not on any bill is left alone."""
    m, room, w, keeper = _stocked_shop()
    sword = _item(int(O.SHORT_SWORD), dknown=True, id="ac3", spe=0)
    w.obj_tables.name_known.add(int(O.SHORT_SWORD))
    addinv(w, "player", sword)  # carried, but not billed
    shk.alter_cost(w, sword, 0)
    assert sword.id not in keeper.eshk.bill


def test_enchant_armor_scroll_reprices_a_billed_item():
    """The EF_PAY half: reading a scroll of enchant armour on a worn,
    billed armour reprices the bill (the scroll calls alter_cost)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    armor_otyp = _find_armor_cost(1)
    armor = _item(armor_otyp, dknown=True, id="ea1", spe=0, owornmask=W_ARMC)
    w.obj_tables.name_known.add(armor_otyp)
    _bill_item(w, keeper, armor)
    old_price = eshk.bill[armor.id].price
    scroll = _item(int(O.SCR_ENCHANT_ARMOR), id="scr1")
    scroll.scroll_type = ScrollType.ENCHANT_ARMOR
    addinv(w, "player", scroll)
    from core.scrolls import read_scroll

    read_scroll(w, "player", scroll.id, _rng())
    assert armor.spe > 0  # the enchant landed
    # the bill price was repriced up (alter_cost, the EF_PAY half)
    assert eshk.bill[armor.id].price > old_price
    assert_item_locations(w)


def test_a_closed_shop_does_not_bill_or_block():
    """inhishop's closed state: a keeper that is not at home (teleported
    away) makes the shop closed -- no billing (costly_spot False) and no
    door block."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    assert shk.inhishop(w, keeper) is True  # at home
    keeper.pos = (1, 1)  # teleported away
    assert shk.inhishop(w, keeper) is False  # closed
    spot = _inside_shop_pos(room)
    assert shk.costly_spot(w, *spot) is False
    w.hero.pos = spot
    w.hero.in_shop = m.room_of(room)
    door = eshk.shd
    assert shk.block_door(w, door[0], door[1]) is None


def test_paybill_inherits_on_death_in_the_shop():
    """paybill: die in the shop with a peaceful keeper and nothing owed
    -> the keeper gratefully inherits all your possessions (the pack
    moves to the keeper)."""
    m, room, w, keeper = _stocked_shop()
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    w.hero.in_shop = m.room_of(room)
    gear = _item(int(O.SHORT_SWORD), id="inh1")
    addinv(w, "player", gear)
    assert keeper.mpeaceful is True
    events = shk.paybill(w, 1)  # the hero dies
    msgs = _msgs(events)
    assert any("gratefully inherits" in x for x in msgs)
    assert gear.carrier == keeper.id
    assert gear in keeper.inventory
    assert gear not in w.hero.inventory
    assert_item_locations(w)


def test_paybill_takes_the_owed_amount():
    """paybill: the hero is not in the shop but owes a debt (robbed) and
    carries enough gold -> the keeper takes the owed amount (money2mon),
    and the paid-in-full keeper is pacified."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    eshk.robbed = 50
    eshk.following = True
    keeper.mpeaceful = False
    gold = _item(int(O.GOLD_PIECE), quan=100, id="pb1")
    addinv(w, "player", gold)
    w.hero.in_shop = NO_ROOM  # not in the shop
    keeper_before = _purse(keeper)
    events = shk.paybill(w, 1)
    msgs = _msgs(events)
    assert any("takes the 50" in x for x in msgs)
    assert _purse(keeper) == keeper_before + 50
    assert money_cnt(w.hero) == 50
    assert eshk.robbed == 0
    assert keeper.mpeaceful is True  # pacified
    assert eshk.following is False
    assert_item_locations(w)


def test_paybill_takes_everything_when_in_the_shop():
    """paybill: die in the shop with an unpaid bill -> the keeper takes
    all your possessions (the gold moves with the pack, the debt is
    reduced by the gold)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.POT_HEALING), dknown=True, id="pb2")
    w.obj_tables.name_known.add(int(O.POT_HEALING))
    _bill_item(w, keeper, item)
    gold = _item(int(O.GOLD_PIECE), quan=200, id="pb3")
    addinv(w, "player", gold)
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    w.hero.in_shop = m.room_of(room)
    debt = shk.shop_debt(eshk)
    assert debt > 0
    keeper_before = _purse(keeper)
    events = shk.paybill(w, 1)
    msgs = _msgs(events)
    assert any("takes all your possessions" in x for x in msgs)
    # the whole pack (including the gold) moved to the keeper
    assert item.carrier == keeper.id
    assert gold.carrier == keeper.id
    assert not w.hero.inventory
    assert _purse(keeper) == keeper_before + 200
    # the gold covered part of the debt
    assert eshk.robbed == max(0, debt - 200)
    assert_item_locations(w)


def test_paybill_does_nothing_when_there_is_no_keeper():
    """No shopkeeper on the level: paybill takes nothing."""
    m, room, w, keeper = _stocked_shop()
    keeper.alive = False
    gear = _item(int(O.SHORT_SWORD), id="pb4")
    addinv(w, "player", gear)
    events = shk.paybill(w, 1)
    assert _msgs(events) == []
    assert gear.carrier == "player"  # the hero keeps the pack
    assert_item_locations(w)


# ------------------------------------------------------------
# phase 4d: the keeper's behaviour (the dialogue, the honorific,
# the movement, the anger state machine)
# ------------------------------------------------------------


def test_shkname_is_the_honorific():
    """shkname: a general name ('_' / '|' prefix, or none) takes the
    Mr. / Ms. honorific from the keeper's gender; a personal name
    ('-' / '+' / '=' prefix) is the bare name (C: the prefix codes of
    shknam.c 21-30 + the call-site honorific of end.c 268-272)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    cases = [
        ("_Adele", True, "Ms. Adele"),
        ("|Brenda", False, "Mr. Brenda"),
        ("-Lucrezia", True, "Lucrezia"),
        ("+Dirk", False, "Dirk"),
        ("=Quinn", True, "Quinn"),
        ("Asidonhopo", False, "Mr. Asidonhopo"),  # no prefix: general
    ]
    for name, female, display in cases:
        eshk.shknam = name
        keeper.female = female
        assert shk.shkname(keeper) == display


def test_the_keeper_greets_the_hero_on_entry():
    """The entry greeting (C: u_entered_shop): a peaceful keeper at home
    welcomes the hero, the visit is counted and the customer recorded
    (the fixed stand-in, C's plname slot is a named skip)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    events = shk.track_shop(w, inside)
    msgs = _msgs(events)
    assert any("Welcome to " in x for x in msgs)
    assert eshk.visitct == 1  # the first visit
    assert eshk.customer != ""  # the customer is recorded


def test_a_second_entry_says_welcome_again():
    """The visitct ' again' of a repeat (C: the visitct++ post-increment
    of the Welcome line)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    shk.track_shop(w, inside)
    w.hero.pos = (1, 1)
    shk.track_shop(w, (1, 1))  # leave (no bill: no robbery)
    w.hero.pos = inside
    msgs = _msgs(shk.track_shop(w, inside))
    assert any("Welcome again to " in x for x in msgs)
    assert eshk.visitct == 2


def test_an_angry_keeper_greets_with_dare_return():
    """An established account (the customer already recorded -- the
    new-customer reset would pacify first, as in C): the angry keeper
    greets with the dare-return line."""
    m, room, w, keeper = _stocked_shop()
    keeper.mpeaceful = False
    keeper.eshk.customer = "hero"  # the established account
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    msgs = _msgs(shk.track_shop(w, inside))
    assert any("You dare return to " in x for x in msgs)


def test_a_surcharge_keeper_greets_unwelcoming():
    m, room, w, keeper = _stocked_shop()
    keeper.eshk.customer = "hero"  # the established account
    keeper.eshk.surcharge = True
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    msgs = _msgs(shk.track_shop(w, inside))
    assert any("seems unwelcoming" in x for x in msgs)


def test_a_robbed_keeper_mutters_imprecations():
    m, room, w, keeper = _stocked_shop()
    keeper.eshk.robbed = 30
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    msgs = _msgs(shk.track_shop(w, inside))
    assert any("mutters imprecations against shoplifters" in x for x in msgs)


def test_a_sleeping_keeper_does_not_greet():
    """C: u_entered_shop's no-dialog guard (muteshk, which for a keeper
    is the helpless = sleep state): the reset still records the
    customer, but no line comes out."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    keeper.sleeping = 5
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    events = shk.track_shop(w, inside)
    assert _msgs(events) == []
    assert eshk.customer != ""  # the customer IS recorded


def test_a_following_keeper_does_not_greet():
    """C: u_entered_shop's no-dialog guard, the following half: an
    established account still in pursuit (the customer already
    recorded) does not talk on re-entry."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    eshk.customer = "hero"  # the established account (no reset)
    eshk.following = True
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    assert _msgs(shk.track_shop(w, inside)) == []


def test_a_dead_keeper_s_shop_is_deserted():
    """C: u_entered_shop's !inhishop half (the dead keeper, shkgone):
    no monster left in the room -> the 'is deserted' line."""
    m, room, w, keeper = _stocked_shop()
    for mon in _mons(w, 1):  # the mimics too: an empty shop
        mon.alive = False
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    msgs = _msgs(shk.track_shop(w, inside))
    assert msgs == ["This shop is deserted."]


def test_a_keeper_off_its_square_leaves_the_shop_untended():
    """C: deserted_shop's monster counts: a keeper off its square is
    not at home, and a monster in the room is sensed as untended
    (visible) or 'seems to be untended' (not yet seen -- no vision
    recalc yet)."""
    m, room, w, keeper = _stocked_shop()
    keeper.pos = (1, 1)  # off its square (the shop is closed)
    intruder = make_monster(kind="goblin", pos=(room.hx - 1, room.hy - 1))
    w.actors[intruder.id] = intruder
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    msgs = _msgs(shk.shk_entered(w, keeper))
    assert msgs == ["This shop seems to be untended."]  # no vision yet
    vision_recalc(w)
    msgs = _msgs(shk.shk_entered(w, keeper))
    assert msgs == ["This shop is untended."]


def test_leaving_with_a_bill_gets_the_warning_first():
    """The leave warning (C: u_left_shop) lands BEFORE the 4c robbery's
    lines (the named collapse of C's boundary grace: pyhack's door
    square is outside, so both fire on the same move)."""
    m, room, w, keeper = _stocked_shop()
    item = _item(int(O.APPLE), dknown=True, id="warn1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    shk.track_shop(w, inside)  # enter
    w.hero.pos = (1, 1)
    msgs = _msgs(shk.track_shop(w, (1, 1)))  # leave with the bill
    assert any("Please pay before leaving." in x for x in msgs)
    warn_i = next(i for i, x in enumerate(msgs) if "Please pay" in x)
    rob_i = next(i for i, x in enumerate(msgs) if "stole" in x)
    assert warn_i < rob_i  # the warning is the lead-in


def test_a_surcharged_leave_gets_the_upset_warning():
    """C: u_left_shop's upset half: a keeper that is already watching
    (the surcharge) says the 'Don't you leave without paying!' line."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="warn2")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    eshk.surcharge = True
    w.hero.pos = _inside_shop_pos(room)
    w.hero.in_shop = m.room_of(room)
    msgs = _msgs(shk.track_shop(w, (1, 1)))  # leave with the bill
    assert any("Don't you leave without paying!" in x for x in msgs)
    assert any("stole" in x for x in msgs)


def test_talk_answers_from_the_keeper_of_the_shop():
    """C: 't' -> dotal, the shopkeeper half: inside the shop the keeper
    answers (a peaceful keeper with a full account talks shoplifting);
    a turn is spent, as C's talk does."""
    m, room, w, keeper = _stocked_shop()
    w.hero.pos = (10, 8)  # inside, not adjacent to keeper or mimics
    w.hero.in_shop = m.room_of(room)
    events = step(w, TalkCommand(), _rng())
    msgs = _msgs(events)
    assert any("talks about the problem of shoplifters" in x for x in msgs)


def test_talk_finds_an_adjacent_keeper_outside_the_shop():
    """Outside the shop (the door square is strictly outside), a keeper
    adjacent to the hero answers."""
    m, room, w, keeper = _stocked_shop()
    door = keeper.eshk.shd  # the door square, outside the shop
    w.hero.pos = door
    msgs = _msgs(shk.talk(w, _rng()))
    assert len(msgs) == 1
    assert "talks about the problem of shoplifters" in msgs[0]


def test_talk_with_no_keeper_says_no_one():
    m, room, w, keeper = _stocked_shop()
    w.hero.pos = (1, 1)  # outside the shop, far from every keeper
    assert _msgs(shk.talk(w, _rng())) == ["No one around to talk to."]


def test_shk_chat_follows_the_anger_ladder():
    """shk_chat's branch ladder in C's order: the anger lines
    (non-paying when robbed, else rude), the pursuit, the bill total,
    the debit, the credit, the robbery, the surcharge, the purse lines
    (under 50 / over 4000) and the shoplifters fallback."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    purse = next(it for it in keeper.inventory if it.oclass == int(ObjClass.COIN))

    def chat() -> str:
        msgs = _msgs(shk.shk_chat(w, keeper))
        assert len(msgs) == 1
        return msgs[0]

    keeper.mpeaceful = False
    eshk.robbed = 40
    assert "dislikes non-paying customers" in chat()
    eshk.robbed = 0
    assert "dislikes rude customers" in chat()
    keeper.mpeaceful = True
    eshk.following = True
    assert "Didn't you forget to pay?" in chat()
    eshk.following = False
    item = _item(int(O.APPLE), dknown=True, id="chat1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    total = shk.addupbill(eshk) + eshk.debit
    assert f"your bill comes to {total}" in chat()
    shk.sub_one_frombill(eshk, item)
    eshk.debit = 33
    assert "you owe him 33" in chat()  # the keeper is male
    eshk.debit = 0
    eshk.credit = 77
    assert "use your 77" in chat()
    eshk.credit = 0
    eshk.robbed = 12
    assert "complains about a recent robbery" in chat()
    eshk.robbed = 0
    eshk.surcharge = True
    assert "watching you carefully" in chat()
    eshk.surcharge = False
    purse.quan = 10
    assert "business is bad" in chat()
    purse.quan = 5000
    assert "business is good" in chat()
    purse.quan = 3340  # the seeded capital: in between
    assert "talks about the problem of shoplifters" in chat()
    assert_item_locations(w)


def test_shk_chat_for_a_non_keeper():
    """C: shk_chat's !isshk half (the animated shopkeeper statue):
    a shopkeeper-typed monster that is not a keeper asks about
    untended shops."""
    m, room, w, keeper = _stocked_shop()
    statue = make_monster(kind="goblin", pos=(13, 9))
    w.actors[statue.id] = statue
    msgs = _msgs(shk.shk_chat(w, statue))
    assert len(msgs) == 1
    assert "asks whether you've seen any untended shops" in msgs[0]


def test_a_following_keeper_chases_the_hero():
    """C: shk_move's following half: after a robbery the keeper pursues
    the hero (core.step's greedy single step on the monster turn)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    eshk.following = True
    keeper.mpeaceful = False
    hero_pos = (10, 8)
    w.hero.pos = hero_pos
    before = distmin(keeper.pos, hero_pos)
    step(w, WaitCommand(), _rng())
    assert distmin(keeper.pos, hero_pos) == before - 1


def test_an_angry_keeper_pursues_a_hero_it_can_see():
    """C: shk_move's anger half: an angry keeper that can see the hero
    (the hero's sight, recalculated in step) pursues it."""
    m, room, w, keeper = _stocked_shop()
    keeper.mpeaceful = False  # angry, not following
    hero_pos = (10, 8)
    w.hero.pos = hero_pos
    before = distmin(keeper.pos, hero_pos)
    step(w, WaitCommand(), _rng())
    assert distmin(keeper.pos, hero_pos) == before - 1


def test_a_displaced_keeper_walks_home():
    """C: shk_move's way home: a settled keeper off its own square walks
    back to it (the greedy single step)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    keeper.pos = (12, 8)
    w.hero.pos = (10, 8)  # not adjacent (the keeper would attack)
    before = distmin(keeper.pos, eshk.shk)
    step(w, WaitCommand(), _rng())
    assert distmin(keeper.pos, eshk.shk) == before - 1


def test_a_keeper_at_home_stands_still():
    """C: shk_move's rest: a settled keeper on its own square does not
    wander (unlike the other monsters, which random-walk)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    assert keeper.pos == eshk.shk
    w.hero.pos = (10, 8)
    step(w, WaitCommand(), _rng())
    assert keeper.pos == eshk.shk  # no wander


def test_angry_shk_exists_tracks_the_anger():
    """angry_shk_exists (C 1343): any shopkeeper with NOTANGRY FALSE."""
    m, room, w, keeper = _stocked_shop()
    assert shk.angry_shk_exists(w) is False
    shk.rile_shk(keeper)
    assert shk.angry_shk_exists(w) is True
    shk.pacify_shk(keeper, True)
    assert shk.angry_shk_exists(w) is False


def test_pacify_shk_round_trips_the_surcharge():
    """rile_shk's (price + 2) // 3 markup is undone by pacify_shk's
    (price + 3) // 4 reduction (a 100 -> 133 -> 100 round trip)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    item = _item(int(O.APPLE), dknown=True, id="pc1")
    w.obj_tables.name_known.add(int(O.APPLE))
    _bill_item(w, keeper, item)
    base = eshk.bill[item.id].price
    shk.rile_shk(keeper)
    marked = eshk.bill[item.id].price
    assert marked == base + (base + 2) // 3
    shk.pacify_shk(keeper, True)  # the new-customer reset's clear
    assert eshk.bill[item.id].price == base
    assert eshk.surcharge is False
    # make_happy_shk's pacify keeps the markup (the shop's memory)
    shk.rile_shk(keeper)
    marked = eshk.bill[item.id].price
    shk.make_happy_shk(w, keeper)
    assert eshk.bill[item.id].price == marked
    assert eshk.surcharge is True
    assert_item_locations(w)


def test_rouse_shk_wakes_a_sleeping_keeper():
    """C: rouse_shk: a sleeping keeper wakes; the 'wakes up' line comes
    out when the keeper is visible (the hero's current sight)."""
    m, room, w, keeper = _stocked_shop()
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    vision_recalc(w)
    keeper.sleeping = 5
    msgs = _msgs(shk.rouse_shk(w, keeper, True))
    assert len(msgs) == 1
    assert "wakes up" in msgs[0]
    assert keeper.sleeping == 0
    assert _msgs(shk.rouse_shk(w, keeper, True)) == []  # already awake
    # an unseen keeper (the closed door blocks the sight) wakes silently
    keeper.sleeping = 5
    w.hero.pos = (1, 1)  # outside the room, the door is closed
    vision_recalc(w)
    assert _msgs(shk.rouse_shk(w, keeper, True)) == []
    assert keeper.sleeping == 0


def test_make_happy_shk_calmes_a_keeper_at_home():
    """C: make_happy_shk, the at-home half: the anger and the pursuit
    clear, the robbery is forgiven, and the angry keeper calms down."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    keeper.mpeaceful = False
    eshk.following = True
    eshk.robbed = 40
    assert keeper.pos == eshk.shk
    msgs = _msgs(shk.make_happy_shk(w, keeper))
    assert any("calms down" in x for x in msgs)
    assert keeper.mpeaceful is True
    assert eshk.following is False
    assert eshk.robbed == 0
    assert keeper.pos == eshk.shk


def test_make_happy_shk_sends_a_keeper_home():
    """C: make_happy_shk's home_shk half (reduced to a square set): a
    satisfied keeper off its square is set on it again, with the
    'returns to ... shop' line (the vanished / cross-level / kops
    halves are named skips)."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    keeper.mpeaceful = False
    keeper.pos = (1, 1)  # OUTSIDE the shop (inhishop False: the chase)
    w.hero.pos = _inside_shop_pos(room)
    vision_recalc(w)
    assert w.monster_at(eshk.shk) is None  # the home square is free
    msgs = _msgs(shk.make_happy_shk(w, keeper))
    assert keeper.pos == eshk.shk
    assert any("returns to " in x for x in msgs)
    assert keeper.mpeaceful is True


def test_do_pay_compensates_a_robbery_and_calmes_the_keeper():
    """The 4d satisfaction of do_pay (C's dopay robbery branch, reduced
    to pay-all): a following / robbed keeper is paid the full bill AND
    the full robbery, and make_happy_shk settles the keeper."""
    m, room, w, keeper, eshk, it1, it2 = _billed_shop()
    eshk.robbed = 50
    eshk.following = True
    keeper.mpeaceful = False
    gold = _item(int(O.GOLD_PIECE), quan=1000, id="payrob1")
    addinv(w, "player", gold)
    total = shk.shop_debt(eshk) + eshk.robbed
    money_before = money_cnt(w.hero)
    purse_before = _purse(keeper)
    events = shk.do_pay(w, _rng())
    msgs = _msgs(events)
    assert any("You compensate " in x and "50" in x for x in msgs)
    assert any("calms down" in x for x in msgs)
    assert any("Thank you for shopping" in x for x in msgs)
    assert keeper.mpeaceful is True  # pacified
    assert eshk.following is False
    assert eshk.robbed == 0
    assert eshk.billct == 0  # the bill is settled
    assert money_cnt(w.hero) == money_before - total
    assert _purse(keeper) == purse_before + total
    assert_item_locations(w)


def test_a_new_customer_resets_the_keeper():
    """C: u_entered_shop's new-customer reset (the single-player
    reduction of the plname comparison): the first entry of a fresh
    account clears the pursuit and the surcharge (pacify_shk with the
    surcharge cleared) and restarts the visit counter."""
    m, room, w, keeper = _stocked_shop()
    eshk = keeper.eshk
    eshk.robbed = 40  # the robbery ledger survives the reset (C's)
    eshk.following = True
    eshk.surcharge = True
    eshk.visitct = 7
    keeper.mpeaceful = False
    eshk.customer = ""  # a fresh customer (C: the plname comparison)
    inside = _inside_shop_pos(room)
    w.hero.pos = inside
    events = shk.track_shop(w, inside)
    assert eshk.following is False
    assert eshk.surcharge is False
    assert eshk.visitct == 0
    assert keeper.mpeaceful is True
    # the ladder lands on the robbed line (the welcome is later)
    assert any("mutters imprecations against shoplifters" in x for x in _msgs(events))
