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
from core.hacklib import distmin
from core.mklev import add_door, add_room, blank_map, makelevel, topologize
from core.monst import MONS
from core.monst_defs import PM_SHOPKEEPER, S_MIMIC
from core.objects import O, ObjClass
from core.rnd import Rng
from core.shknam_data import (
    FODDER_SHOP,
    SHKARMORS,
    SHOPTYPES,
    UNIQUE_SHOP_START,
    VEGETARIAN_CLASS,
)
from core.types import (
    ANY_SHOP,
    FILL_NORMAL,
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
from conftest import assert_item_locations, make_hero

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
    assert shk.get_shop_item(_FixedRng(71), FODDER_SHOP) == (
        -int(O.POT_FRUIT_JUICE)
    )


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
