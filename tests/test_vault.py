"""Tests for the vault (PLAN-SPECIAL-ROOMS.md phase 5): create_vault
(the 2x2 reservation in makerooms), the vault block of makelevel (the
sealed, lit VAULT room, the double-filled gold, the vtele entrance,
the shop-roll room threshold) and makevtele (the teleport niche).

What must hold: the reservation carves the free rectangle but adds no
room and paints no terrain (C's scratch-slot write); makelevel re-adds
the room as the level's LAST room (after the sort and the corridors,
so nothing is dug into it) -- a sealed, lit 2x2 VAULT with no door,
needfill FILL_NORMAL (never cleared in C), flags.has_vault, and one
gold pile per interior square that is the sum of C's TWO fills (the
inline fill + the end-of-level fill, merged per square by mkgold:
two rn1(lev * 100, 51) draws each); the vault's ring is stone (no
corridor within the kept margin); makevtele digs the SCORR niche with
its TELEPORTATION trap behind a secret door (the way in); and the
vault's `++room_threshold` raises the shop roll from three rooms to
four.

The 80x21 grid is C's dungeon size: the 40x20 demo grid usually makes
fewer than six rooms, and the vault attempt only starts at
MAXNROFROOMS / 6 (the C-sized grid makes ~8).
"""

from core.mklev import (
    Rect,
    RectManager,
    add_door,
    add_room,
    blank_map,
    create_vault,
    makerooms,
    makelevel,
    makevtele,
    topologize,
)
from core.objects import O
from core.rnd import Rng
from core.types import (
    FILL_NORMAL,
    Map,
    RoomType,
    TerrainType,
    TrapType,
    World,
)
from conftest import assert_item_locations, make_hero

W, H = 80, 21


def _rng(seed: int = 1) -> Rng:
    return Rng(b"vault-test:%d" % seed)


def _world(m: Map, lev: int, max_lev: int = 20) -> World:
    w = World(map=m)
    w.lev = lev
    w.max_lev = max_lev
    w.actors["player"] = make_hero(pos=(1, 1))
    return w


def _gen(seed: int, lev: int = 5):
    w = _world(blank_map(W, H), lev)
    m = makelevel(w, w.map, _rng(seed), lev)
    return w, m


def _adjacent_sdoor(m, pos):
    x, y = pos
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if (
            m.in_bounds((x + dx, y + dy))
            and m.tile_at((x + dx, y + dy)).typ == TerrainType.SDOOR
        ):
            return True
    return False


# ------------------------------------------------------------
# create_vault (C: mklev.c 53 macro = create_room's vault path)
# ------------------------------------------------------------


def test_create_vault_reserves_a_spot_without_adding_a_room():
    """C: the vault path of create_room -- split_rects reserves the
    bounding box (the 2x2 interior + its wall ring), but there is no
    room record and no terrain: the position is the scratch-slot write
    only, and makelevel() re-adds the room later."""
    m = blank_map(W, H)
    rects = RectManager(m)
    pos = create_vault(m, rects, _rng(1))
    assert pos is not None
    assert m.rooms == [], "the reservation adds no room record"
    assert all(
        t.typ == TerrainType.STONE for row in m.tiles for t in row
    ), "no terrain is carved yet"
    x, y = pos
    # check_room's clamps: the interior (x..x+1, y..y+1) stays clear of
    # the edge by at least the kept margin
    assert 3 <= x <= m.width - 4 and 2 <= y <= m.height - 4
    box = Rect(x - 1, y - 1, x + 2, y + 2)  # the interior + the wall ring
    assert all(not r.contains(box) for r in rects.rects)


def test_create_vault_refuses_a_too_small_level():
    """C: the size test (hx - lx < dx + 3 + xborder) -- a level whose
    free rectangles are all too small gives up (C's 100-try loop)."""
    m = blank_map(8, 5)
    assert create_vault(m, RectManager(m), _rng(1)) is None


def test_create_vault_refuses_an_empty_rectangle_list():
    """C: `rnd_rect()` is NULL -- "No more rects...", an immediate
    FALSE, not a 100-try loop."""
    m = blank_map(W, H)
    rects = RectManager(m)
    rects.rects = []
    assert create_vault(m, rects, _rng(1)) is None


def test_makerooms_reserves_the_vault_once():
    """C: from MAXNROFROOMS / 6 rooms, the vault gets one chance per
    level (the tried_vault local, the rn2(2) test): on C-sized grids
    some levels reserve the spot and others do not, never two."""
    reserved = 0
    for seed in range(1, 13):
        m = blank_map(W, H)
        rects = RectManager(m)
        pos = makerooms(m, rects, _rng(seed), 5, [])
        reserved += pos is not None
        assert m.rooms, "the level still has its ordinary rooms"
        if pos is not None:
            assert m.rooms and all(r.rtype == RoomType.OROOM for r in m.rooms)
    assert reserved >= 1, "at least one of twelve C-sized levels vaults"


# ------------------------------------------------------------
# the vault block of makelevel (C: mklev.c 1319-1345)
# ------------------------------------------------------------


def test_makelevel_builds_a_sealed_vault_with_gold():
    """C: the fill_vault half -- a sealed, lit 2x2 VAULT room, the
    level's LAST room (added after the sort and the corridors),
    needfill FILL_NORMAL (never cleared), flags.has_vault, and the
    hoard: one pile per interior square, each the sum of C's TWO
    fills (the inline fill + the end-of-level loop, merged per square
    by mkgold) -- two rn1(lev * 100, 51) draws each."""
    vaults = 0
    for seed in range(1, 13):
        w, m = _gen(seed, lev=5)
        vrooms = [r for r in m.rooms if r.rtype == RoomType.VAULT]
        if not vrooms:
            continue
        vaults += 1
        assert len(vrooms) == 1, "one vault per level (C: tried_vault)"
        room = vrooms[0]
        assert (room.hx - room.lx, room.hy - room.ly) == (1, 1), "2x2 interior"
        assert room.rlit, "C: add_room(..., TRUE, VAULT, FALSE)"
        assert room.needfill == FILL_NORMAL, "C never clears it"
        assert room.doorct == 0, "nothing is dug into the vault"
        assert m.rooms[-1] is room, "added after the sort and corridors"
        assert m.flags.has_vault
        # the hoard: one pile on every interior square (mkgold merges
        # the two fills per square), each pile the sum of two draws
        squares = [
            (x, y)
            for x in range(room.lx, room.hx + 1)
            for y in range(room.ly, room.hy + 1)
        ]
        gold = [
            it
            for it in w.items.values()
            if it.lev == 5 and it.otyp == int(O.GOLD_PIECE) and it.pos in set(squares)
        ]
        assert len(gold) == 4
        for pile in gold:
            assert 102 <= pile.quan <= 2 * (5 * 100 + 50)
        # sealed: no corridor (or niche corridor) within one square of
        # the bounding box -- the kept margin is all stone
        for x in range(room.lx - 2, room.hx + 3):
            for y in range(room.ly - 2, room.hy + 3):
                if not m.in_bounds((x, y)):
                    continue
                assert m.tile_at((x, y)).typ not in (
                    TerrainType.CORR,
                    TerrainType.SCORR,
                ), (x, y)
        assert_item_locations(w)
    assert vaults >= 1, "at least one of twelve C-sized levels vaults"


def test_makevtele_digs_a_teleport_niche_behind_a_secret_door():
    """C: makevtele() = makeniche(TRAP_TELEPORTATION) -- the SCORR
    niche with its TELEPORTATION trap, a secret door in front (the
    way into an otherwise sealed vault)."""
    m = blank_map(W, H)
    room = add_room(m, 10, 5, 20, 12, True, RoomType.OROOM, False)
    topologize(m, room)
    w = _world(m, 5)
    makevtele(w, m, _rng(1), 5, 5)
    tps = [t for t in w.traps.values() if t.trap_type == TrapType.TELEPORTATION]
    assert len(tps) == 1
    pos = tps[0].pos
    assert m.tile_at(pos).typ == TerrainType.SCORR
    assert _adjacent_sdoor(m, pos)


def test_add_vault_adds_the_room_and_maybe_the_entrance():
    """The vault block, directly (one fill, not makelevel's two): the
    sealed lit 2x2 room with its inline gold (ONE rn1(lev * 100, 51)
    draw per square -- the second fill is the end-of-level loop's),
    and the vtele niche when the 2-in-3 roll says so."""
    from core.mklev import _add_vault

    niched = 0
    for seed in range(1, 7):
        m = blank_map(W, H)
        rects = RectManager(m)
        # one ordinary room for the vtele niche to dig into (C's
        # makeniche skips non-OROOM rooms)
        add_room(m, 8, 4, 18, 10, True, RoomType.OROOM, False)
        topologize(m, m.rooms[0])
        w = _world(m, 5)
        pos = create_vault(m, rects, _rng(seed))
        assert pos is not None
        assert _add_vault(w, m, rects, _rng(seed), 5, 5, pos) is True
        room = m.rooms[-1]
        assert room.rtype == RoomType.VAULT
        assert (room.hx - room.lx, room.hy - room.ly) == (1, 1)
        assert room.rlit and room.needfill == FILL_NORMAL and room.doorct == 0
        assert m.flags.has_vault
        squares = [
            (x, y)
            for x in range(room.lx, room.hx + 1)
            for y in range(room.ly, room.hy + 1)
        ]
        gold = [
            it
            for it in w.items.values()
            if it.lev == 5 and it.otyp == int(O.GOLD_PIECE) and it.pos in set(squares)
        ]
        assert len(gold) == 4
        for pile in gold:
            assert 51 <= pile.quan <= 5 * 100 + 50, "one draw per square here"
        for trap in w.traps.values():
            if trap.trap_type == TrapType.TELEPORTATION:
                assert m.tile_at(trap.pos).typ == TerrainType.SCORR
                assert _adjacent_sdoor(m, trap.pos)
                niched += 1
                break
    assert niched >= 1, "the 2-in-3 vtele roll fires over six levels"


def test_add_vault_refuses_without_a_reservation():
    """C: `if (do_vault())` -- no reservation, no vault, no draws."""
    from core.mklev import _add_vault

    m = blank_map(W, H)
    rects = RectManager(m)
    w = _world(m, 5)
    assert _add_vault(w, m, rects, _rng(1), 5, 5, None) is False
    assert m.rooms == [] and not m.flags.has_vault
    assert not w.items


# ------------------------------------------------------------
# the ++room_threshold (C: the vault block feeds the shop roll)
# ------------------------------------------------------------


class _ShopRng:
    """The shop-roll draws: rnd(100) -> 50 (mkshop's type walk lands
    mid-table), rn2(depth) -> 0 (< 3, the shop roll is taken)."""

    def rnd(self, n: int) -> int:
        assert 1 <= 50 <= n
        return 50

    def rn2(self, n: int) -> int:
        return 0

    def rn1(self, n: int, x: int) -> int:
        return x


def _three_room_map():
    m = blank_map(W, H)
    for lx, hx in ((4, 12), (16, 24), (28, 36)):
        room = add_room(m, lx, 4, hx, 9, True, RoomType.OROOM, False)
        topologize(m, room)
        add_door(m, lx, 3, room)
    return m


def test_the_vault_raises_the_shop_room_threshold():
    """C: the vault block's `++room_threshold` -- a level with a vault
    needs FOUR rooms for the shop roll, not three: the same 3-room
    level claims a shop at threshold 3 and refuses it at 4 (the
    short-circuit takes no draw, so the refusal consumes nothing).

    The depth is 4 so that a refused shop also refuses the rest of the
    ladder (the court needs depth > 4), keeping the test about the
    shop branch alone.
    """
    from core.mklev import _roll_special_room

    m1 = _three_room_map()
    w1 = _world(m1, 4)
    _roll_special_room(w1, m1, _ShopRng(), 4, [], 4, threshold=3)
    assert any(r.rtype >= RoomType.SHOPBASE for r in m1.rooms)

    m2 = _three_room_map()
    w2 = _world(m2, 4)
    _roll_special_room(w2, m2, _ShopRng(), 4, [], 4, threshold=4)
    assert all(r.rtype == RoomType.OROOM for r in m2.rooms)
