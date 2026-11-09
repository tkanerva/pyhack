"""Tests for the priest system (core.priest) and the temple room
(core.mkroom.mktemple) -- PLAN-SPECIAL-ROOMS.md phase 1.

What must hold: a temple is a room with exactly one ALTAR (the
shrine) carrying AM_SHRINE + a legal alignment, and a peaceful
priest who knows the room (the Epri extra) standing on its 1-square
ring; entering a tended temple gives the pilgrim message and the
peace / forbidding feeling, an untended one the C eerie lines and a
1-in-5 hostile ghost; and #pray / #offer refuse with C's own
misaligned-altar line until src/pray.c lands.
"""

from core import mkroom, priest
from core.commands import MoveCommand, OfferCommand, PrayCommand
from core.events import MessageEvent
from core.mklev import add_door, add_room, blank_map, topologize
from core.monst_defs import (
    A_CHAOTIC,
    A_LAWFUL,
    A_NEUTRAL,
    AM_LAWFUL,
    AM_NEUTRAL,
    AM_SHRINE,
    amask2align,
)
from core.objects import ObjClass
from core.rnd import Rng
from core.step import step
from core.types import DoorMask, RoomType, TerrainType, Tile, World
from conftest import assert_item_locations, make_hero

W, H = 40, 20


def _rng(seed: int = 1) -> Rng:
    """The temple draws through the NetHack rng API (rn2 / rnd / rn1),
    i.e. core.rnd.Rng -- not random.Random."""
    return Rng(b"priest-test:%d" % seed)


def _room_map(rtype: RoomType = RoomType.OROOM):
    """A single lit 7x5 room (floor 5..11 by 4..8, center 8,6) with one
    door, like the other room tests (tests/test_mkroom.py)."""
    m = blank_map(W, H)
    room = add_room(m, 5, 4, 11, 8, True, rtype, False)
    topologize(m, room)
    add_door(m, 5, 3, room)
    return m, room


def _world(m, hero_pos=(1, 1)):
    w = World(map=m)
    w.actors["player"] = make_hero(pos=hero_pos)
    return w


def _shrine(m):
    """The one ALTAR on the map (a temple has exactly one)."""
    return next(
        (x, y)
        for y in range(H)
        for x in range(W)
        if m.tile_at((x, y)).typ == TerrainType.ALTAR
    )


def _texts(world_events) -> list:
    return [e.text for e in world_events if isinstance(e, MessageEvent)]


# ------------------------------------------------------------
# induced_align (C: dungeon.c)
# ------------------------------------------------------------


def test_induced_align_is_the_three_way_roll_masked():
    """C: induced_align -- no special level and no dungeon alignment
    in pyhack, so the answer is always the temperate-dungeon roll
    masked (1/2/4); over enough seeds all three must come out."""
    masks = {priest.induced_align(_rng(s)) for s in range(30)}
    assert masks == {1, 2, 4}


# ------------------------------------------------------------
# priestini (C: priest.c)
# ------------------------------------------------------------


def test_priestini_places_a_peaceful_priest_by_the_shrine():
    m, room = _room_map()
    w = _world(m)
    pos = (8, 6)  # the room center, C's shrine spot
    m.tile_at(pos).typ = TerrainType.ALTAR
    m.tile_at(pos).altarmask = AM_LAWFUL  # pre-AM_SHRINE, C's order
    p = priest.priestini(w, m, room, pos, False, 1, _rng())
    assert p is not None
    assert p.mdata is not None and p.mdata.pmnames[2] == "aligned cleric"
    assert p.mpeaceful and p.ispriest and p.sleeping == 0
    assert p.malign < 0  # a peaceful monster: bad to kill
    epri = p.epri
    assert epri is not None
    assert epri.shroom == m.room_of(room)
    assert epri.shralign == A_LAWFUL  # amask2align of the mask
    assert epri.shrpos == pos
    assert epri.shrlevel == 1
    # on the 1-square ring around the shrine, never on the shrine
    assert p.pos != pos
    assert max(abs(p.pos[0] - pos[0]), abs(p.pos[1] - pos[1])) <= 1
    # the goodies: 2 to 4 spellbooks (C: rn1(3, 2)), all carried
    books = [it for it in p.inventory if it.oclass == int(ObjClass.SPBOOK)]
    assert 2 <= len(books) <= 4
    assert len(books) == len(p.inventory)
    assert all(it.carrier == p.id for it in p.inventory)
    assert_item_locations(w)


def test_priestini_falls_back_to_the_shrine_square_when_the_ring_fails():
    """C: `if (i == N_DIRS) px = sx, py = sy` -- a shrine walled in on
    all eight sides makes the priest stand on the shrine itself (and a
    priest on a square nobody shares is C's makemon answer)."""
    m, room = _room_map()
    w = _world(m)
    pos = (8, 6)
    m.tile_at(pos).typ = TerrainType.ALTAR
    m.tile_at(pos).altarmask = AM_LAWFUL
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                m.tiles[6 + dy][8 + dx] = Tile(typ=TerrainType.STONE)
    p = priest.priestini(w, m, room, pos, False, 1, _rng())
    # the ring is all stone, so the search lands on the shrine -- and
    # C's makemon at an explicit square does not re-test the terrain
    # (pm_good_location is the caller's contract), so the priest ends
    # up standing on the shrine itself
    assert p is not None and p.pos == pos


# ------------------------------------------------------------
# mktemple (C: mkroom.c)
# ------------------------------------------------------------


def test_mktemple_builds_the_shrine_and_the_priest():
    """PLAN-SPECIAL-ROOMS.md phase 1 tests: exactly one altar at the
    shrine position, AM_SHRINE + a legal alignment; the priest is
    peaceful, of the altar's alignment, on the shrine's ring, and
    knows the room; flags.has_temple."""
    m, room = _room_map()
    w = _world(m)
    claimed = mkroom.mktemple(w, m, [], [], _rng(), 1)
    assert claimed is room
    assert room.rtype == RoomType.TEMPLE
    assert m.flags.has_temple
    altars = [
        (x, y)
        for y in range(H)
        for x in range(W)
        if m.tile_at((x, y)).typ == TerrainType.ALTAR
    ]
    assert len(altars) == 1
    shrine = altars[0]
    mask = m.tile_at(shrine).altarmask
    assert mask & AM_SHRINE
    align = amask2align(mask & ~AM_SHRINE)
    assert align in (A_CHAOTIC, A_NEUTRAL, A_LAWFUL)
    # the shrine is inside the room (C: the center, or a free square)
    assert room.contains(shrine)
    p = priest.findpriest(w, 1, m.room_of(room))
    assert p is not None
    assert p.epri is not None and p.epri.shrpos == shrine
    assert p.epri.shralign == align
    assert p.lev == 1 and p.mpeaceful
    assert max(abs(p.pos[0] - shrine[0]), abs(p.pos[1] - shrine[1])) <= 1
    assert priest.has_shrine(p, m)
    assert_item_locations(w)


def test_second_mktemple_on_a_one_room_level_returns_none():
    """C: pick_room(TRUE) -- once the only room is a TEMPLE, a second
    claim finds no ordinary room and answers None (C's NULL) without
    re-stocking or crashing (the plan's phase-1 test)."""
    m, room = _room_map()
    w = _world(m)
    first = mkroom.mktemple(w, m, [], [], _rng(), 1)
    assert first is room
    second = mkroom.mktemple(w, m, [], [], _rng(2), 1)
    assert second is None
    altars = sum(
        1
        for y in range(H)
        for x in range(W)
        if m.tile_at((x, y)).typ == TerrainType.ALTAR
    )
    assert altars == 1


# ------------------------------------------------------------
# intemple (C: priest.c, reduced)
# ------------------------------------------------------------


def _tended_temple():
    m, room = _room_map()
    w = _world(m)
    mkroom.mktemple(w, m, [], [], _rng(), 1)
    return w, m, room


def test_intemple_tended_temple_gives_the_entry_and_the_peace():
    w, m, room = _tended_temple()
    shrine = _shrine(m)
    # the hero is co-aligned with the altar: the C peace branch
    w.hero_align = amask2align(m.tile_at(shrine).altarmask & ~AM_SHRINE)
    texts = _texts(priest.intemple(w, room, _rng()))
    assert "Pilgrim, you enter a sacred place!" in texts
    assert "You experience an unusual sense of peace." in texts


def test_intemple_gives_the_forbidding_feeling_when_misaligned():
    w, m, room = _tended_temple()
    shrine = _shrine(m)
    align = amask2align(m.tile_at(shrine).altarmask & ~AM_SHRINE)
    w.hero_align = A_CHAOTIC if align != A_CHAOTIC else A_LAWFUL
    texts = _texts(priest.intemple(w, room, _rng()))
    assert "Pilgrim, you enter a sacred place!" in texts
    assert "You have a forbidding feeling..." in texts


def test_intemple_desecrated_when_the_shrine_is_gone():
    """C: has_shrine() -- a temple whose shrine is no longer an
    aligned altar is "desecrated" (and forbidding)."""
    w, m, room = _tended_temple()
    shrine = _shrine(m)
    m.tile_at(shrine).typ = TerrainType.ROOM
    texts = _texts(priest.intemple(w, room, _rng()))
    assert "Pilgrim, you enter a desecrated place!" in texts
    assert "You have a forbidding feeling..." in texts


def test_intemple_untended_temple_is_eerie_and_maybe_ghosted():
    """C: the untended half -- the rn2(4) eerie message, then a 1-in-5
    ghost that appears next to the hero and turns hostile.  Across
    seeds the ghost must come out at least once, and every message is
    one of C's lines."""
    allowed = {
        "You have an eerie feeling...",
        "You feel like you are being watched.",
        "A shiver runs down your spine.",
        "You sense a presence close by!",
        "An enormous ghost appears next to you!",
    }
    ghosts = 0
    for seed in range(30):
        # a TEMPLE room with its shrine, and no priest: untended
        m = blank_map(W, H)
        room = add_room(m, 5, 4, 11, 8, True, RoomType.TEMPLE, False)
        topologize(m, room)
        w = _world(m, hero_pos=(5, 4))
        m.tile_at((8, 6)).typ = TerrainType.ALTAR
        m.tile_at((8, 6)).altarmask = AM_SHRINE | AM_NEUTRAL
        events = priest.intemple(w, room, _rng(seed))
        for text in _texts(events):
            assert text in allowed, text
        ghost = next(
            (
                a
                for a in w.actors.values()
                if not a.is_hero
                and a.mdata is not None
                and a.mdata.pmnames[2] == "ghost"
            ),
            None,
        )
        if ghost is not None:
            ghosts += 1
            assert not ghost.mpeaceful
            hero = w.hero
            assert (
                max(abs(ghost.pos[0] - hero.pos[0]), abs(ghost.pos[1] - hero.pos[1]))
                <= 1
            )
    assert ghosts, "a 1-in-5 ghost over 30 seeds must come out at least once"


# ------------------------------------------------------------
# the refused entry points (C: src/pray.c)
# ------------------------------------------------------------


def test_pray_and_offer_refuse_and_spend_the_turn():
    m, _room = _room_map()
    w = _world(m)
    for cmd in (PrayCommand(), OfferCommand()):
        events = step(w, cmd, _rng())
        assert "You feel you should not do that here." in _texts(events)
    assert w.turn == 2, "the refusals are commands, not listings"


# ------------------------------------------------------------
# the room-entry hook (C: check_special_room, the temple half)
# ------------------------------------------------------------


def test_temple_entry_message_fires_on_the_room_crossing_only():
    m, room = _room_map()
    w = _world(m)
    mkroom.mktemple(w, m, [], [], _rng(), 1)
    # an open doorway on the room's top wall, the hero just outside it;
    # the door keeps the stamped roomno / edge / lit of the wall tile it
    # replaces (C: dosdoor copies them -- room_at must still resolve it)
    wall = m.tiles[3][5]
    m.tiles[3][5] = Tile(
        typ=TerrainType.DOOR,
        door_mask=DoorMask(0),
        roomno=wall.roomno,
        edge=wall.edge,
        lit=wall.lit,
    )
    w.actors["player"] = make_hero(pos=(5, 2))
    # crossing into the temple fires the entry message...
    events = step(w, MoveCommand(0, 1), _rng())
    assert any("Pilgrim, you enter a" in t for t in _texts(events))
    # ...and moving on inside the room does not re-fire it
    events = step(w, MoveCommand(0, 1), _rng())
    assert not any("Pilgrim" in t for t in _texts(events))
