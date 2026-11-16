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
from core.commands import PayCommand
from core.events import MessageEvent
from core.hacklib import distmin
from core.invent import addinv, money_cnt
from core.mklev import add_door, add_room, blank_map, makelevel, topologize
from core.mkobj import coarse_otype, place_object
from core.monst import MONS
from core.monst_defs import PM_SHOPKEEPER, S_MIMIC
from core.objects import BASES, NUM_OBJECTS, OBJECTS, O, ObjClass
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
    Room,
    RoomType,
    Stairway,
    TerrainType,
    Tile,
    World,
)
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
