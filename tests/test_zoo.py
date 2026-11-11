"""Tests for the zoo family (core.mkroom.fill_zoo and the pickers,
core.mkroom.fill_special_room) -- PLAN-SPECIAL-ROOMS.md phase 2.

What must hold: each zoo room type is stocked in C's shape -- one
monster per stocked square (the court's throne square holds the
monarch), the court's THRONE + a hostile asleep monarch with a mace
+ the royal coffers, the ZOO / LEPREHALL gold within the per-square
budget (goldlim = 500 * depth; per square i = the squared dist2 to
the door, i = 5 * depth once i >= goldlim, mkgold(rn1(i, 10)),
goldlim -= i), the morgue's corpses / chests / graves, the beehive's
one queen at the centre, the anthole's single species, the barracks'
squad, the cockatrice nest's statues and their loot, every monster
asleep, the C level flags set (the C switch has no case for the
anthole / cocknest / leprehall), and the room's floor stays
walkable.
"""

from typing import Tuple

from core import mkroom
from core.hacklib import dist2
from core.mklev import add_door, add_room, blank_map, topologize
from core.mkobj import mksobj_at
from core.monst import (
    PM_CAPTAIN,
    PM_FIRE_ANT,
    PM_GIANT_ANT,
    PM_LIEUTENANT,
    PM_SERGEANT,
    PM_SOLDIER,
    PM_SOLDIER_ANT,
)
from core.monst_defs import (
    G_GONE,
    S_CENTAUR,
    S_DRAGON,
    S_GIANT,
    S_GNOME,
    S_GHOST,
    S_HUMANOID,
    S_KOBOLD,
    S_ORC,
    S_TROLL,
    S_WRAITH,
    S_ZOMBIE,
)
from core.objects import O, ObjClass
from core.rnd import Rng
from core.types import (
    NO_MM_FLAGS,
    DoorMask,
    FILL_NORMAL,
    Map,
    Room,
    RoomType,
    TerrainType,
    Tile,
    World,
    space_pos,
)
from conftest import assert_item_locations, make_hero

W, H = 40, 20
LX, LY, HX, HY = 5, 4, 14, 10  # a 10x7 floor: 70 squares
STOCKED = 60  # 70 minus the row under the top-wall door
CENTER = (10, 7)  # the beehive queen square (the room centre)
UNDEAD = (S_GHOST, S_WRAITH, S_ZOMBIE)  # morguemon's depth-5 ladder


def _rng(seed: int = 1) -> Rng:
    return Rng(b"zoo-test:%d" % seed)


def _room_map(door: bool = True) -> Tuple[Map, Room]:
    """A single lit 10x7 room (floor 5..14 by 4..10) with one door on
    the top wall (the shape the other room tests use).  The door tile
    keeps the stamped roomno / edge / lit of the wall it replaces."""
    m = blank_map(W, H)
    room = add_room(m, LX, LY, HX, HY, True, RoomType.OROOM, False)
    topologize(m, room)
    if door:
        wall = m.tiles[LY - 1][LX]
        m.tiles[LY - 1][LX] = Tile(
            typ=TerrainType.DOOR,
            door_mask=DoorMask.CLOSED,
            roomno=wall.roomno,
            edge=wall.edge,
            lit=wall.lit,
        )
        add_door(m, LX, LY - 1, room)
    return m, room


def _world(m: Map, lev: int, birth: int = 0) -> World:
    w = World(map=m)
    w.lev = lev
    w.birth = birth
    w.actors["player"] = make_hero(pos=(1, 1))
    return w


def _claim_and_fill(
    m: Map, room: Room, rtype: RoomType, lev: int, seed: int = 1
) -> World:
    """mkzoo (C's claim: rtype + needfill) and then the end-of-level
    fill_special_room (C: the "Fill all special rooms now" loop)."""
    w = _world(m, lev)
    assert mkroom.mkzoo(m, [], _rng(seed), rtype) is room
    mkroom.fill_special_room(w, _rng(seed), m, [], room, lev)
    return w


def _monsters(w: World, lev: int):
    """The level's monsters standing in the room."""
    return [
        a
        for a in w.actors.values()
        if not a.is_hero
        and a.lev == lev
        and a.pos is not None
        and LX <= a.pos[0] <= HX
        and LY <= a.pos[1] <= HY
    ]


def _items(w: World, lev: int):
    return [it for it in w.items.values() if it.lev == lev]


def _stocked_square(m: Map, room: Room, sh, sx: int, sy: int) -> bool:
    """The rectangular-room skip of fill_zoo (C: the !SPACE_POS or
    door-adjacent continue)."""
    if not space_pos(m.tile_at((sx, sy)).typ):
        return False
    if room.doorct and sh is not None and (
        (sx == room.lx and sh[0] == sx - 1)
        or (sx == room.hx and sh[0] == sx + 1)
        or (sy == room.ly and sh[1] == sy - 1)
        or (sy == room.hy and sh[1] == sy + 1)
    ):
        return False
    return True


def _gold_budget(m: Map, room: Room, sh, ld: int):
    """Replay C's ZOO / LEPREHALL budget (mkroom.c fill_zoo) in C's
    square order: per square i = the squared dist2 to the door
    (i = the budget when the room has no door); when i >= goldlim the
    square takes the flat 5 * depth; goldlim -= i.  Returns the i used
    per square (the per-square gold is rn1(i, 10), i.e. in
    [10, i + 9])."""
    budget = 500 * ld
    caps = {}
    for sx in range(room.lx, room.hx + 1):
        for sy in range(room.ly, room.hy + 1):
            if not _stocked_square(m, room, sh, sx, sy):
                continue
            if room.doorct and sh is not None:
                i = dist2((sx, sy), sh) ** 2
            else:
                i = budget
            if i >= budget:
                i = 5 * ld
            budget -= i
            caps[(sx, sy)] = i
    return caps


# ------------------------------------------------------------
# COURT (C: mkroom.c fill_zoo case COURT + mk_zoo_thronemon)
# ------------------------------------------------------------


def test_court_monarch_sits_asleep_on_the_throne_with_a_mace():
    """PLAN-SPECIAL-ROOMS.md phase 2: one THRONE (written at the
    monarch's square after the stocking loop -- the loop's occupied
    square is why the throne holds exactly one monster), a monarch of
    the four rulers, asleep and hostile, carrying the mace ("Give him
    a sceptre to pound in judgment")."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.COURT, 5)
    thrones = [
        (x, y)
        for y in range(H)
        for x in range(W)
        if m.tile_at((x, y)).typ == TerrainType.THRONE
    ]
    assert len(thrones) == 1
    tx, ty = thrones[0]
    assert LX <= tx <= HX and LY < ty <= HY  # a stocked square
    king = w.monster_at_lev(5, (tx, ty))
    assert king is not None
    assert king.mdata is not None
    assert king.mdata.pmnames[2] in (
        "gnome ruler",
        "dwarf ruler",
        "elven monarch",
        "ogre tyrant",
    )
    assert king.sleeping == 1
    assert not king.mpeaceful
    maces = [it for it in king.inventory if it.otyp == int(O.MACE)]
    assert len(maces) == 1
    assert m.flags.has_court
    assert_item_locations(w)


def test_court_stocks_one_asleep_hostile_monster_per_square():
    """C: courtmon() per square, MM_ASLEEP | MM_NOGRP, and a peaceful
    answer is turned hostile (mpeaceful = 0 + set_malign)."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.COURT, 5)
    mons = _monsters(w, 5)
    assert len(mons) == STOCKED  # the throne square's is the monarch
    assert all(mn.sleeping == 1 for mn in mons)
    assert all(not mn.mpeaceful for mn in mons)
    assert all(mn.mdata is not None for mn in mons)


def test_court_gets_the_royal_coffers():
    """C: a chest with spe = 2 ("so it can be found later") carrying
    rn1(50 * depth, 10) gold, on a free square in the room.  The chest
    itself is mksobj_at(..., init=TRUE), so it may already hold the
    random box loot -- the royal gold is the last content, added
    through add_to_container."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.COURT, 5)
    chests = [
        it
        for it in _items(w, 5)
        if it.otyp == int(O.CHEST)
        and it.pos is not None
        and LX <= it.pos[0] <= HX
        and LY <= it.pos[1] <= HY
    ]
    assert len(chests) == 1
    chest = chests[0]
    assert chest.spe == 2
    royal_gold = w.items[chest.contents[-1]]
    assert royal_gold.otyp == int(O.GOLD_PIECE)
    assert 10 <= royal_gold.quan <= 50 * 5 + 9
    assert_item_locations(w)


# ------------------------------------------------------------
# ZOO / LEPREHALL (C: the gold budget)
# ------------------------------------------------------------


def test_zoo_gold_stays_within_the_per_square_budget():
    """The fiddly part (the plan): goldlim = 500 * depth; per square
    i = the squared dist2 to the door, i = 5 * depth once i >=
    goldlim, mkgold(rn1(i, 10)), goldlim -= i.  Replayed in C's
    square order, every pile is within [10, i + 9] of its square's
    i -- and the ZOO picker is C's NULL, so every square also carries
    the anymon-path monster."""
    m, room = _room_map()
    ld = 5
    w = _claim_and_fill(m, room, RoomType.ZOO, ld)
    caps = _gold_budget(m, room, room.doors[0], ld)
    assert len(caps) == STOCKED
    gold = {it.pos: it for it in _items(w, ld) if it.otyp == int(O.GOLD_PIECE)}
    assert len(gold) == STOCKED  # one pile per stocked square
    for pos, cap in caps.items():
        assert 10 <= gold[pos].quan <= cap + 9
    mons = _monsters(w, ld)
    assert len(mons) == STOCKED
    assert all(mn.sleeping == 1 for mn in mons)
    assert m.flags.has_zoo
    assert_item_locations(w)


def test_zoo_without_a_door_takes_the_flat_budget_per_square():
    """C: a doorless room takes i = goldlim per square, which is >=
    goldlim, so every square gets the flat rn1(5 * depth, 10) and the
    whole floor (70 squares -- there is no door row to skip) is
    stocked.  The claim is written by hand: pick_room() would only
    take a doorless room 1 in 5."""
    m, room = _room_map(door=False)
    ld = 5
    w = _world(m, ld)
    room.rtype = RoomType.ZOO
    room.needfill = FILL_NORMAL
    mkroom.fill_special_room(w, _rng(), m, [], room, ld)
    gold = [it for it in _items(w, ld) if it.otyp == int(O.GOLD_PIECE)]
    assert len(gold) == 70
    assert all(10 <= it.quan <= 5 * ld + 9 for it in gold)
    assert m.flags.has_zoo
    assert_item_locations(w)


def test_leprehall_gets_leprechauns_and_the_zoo_gold():
    m, room = _room_map()
    ld = 5
    w = _claim_and_fill(m, room, RoomType.LEPREHALL, ld)
    mons = _monsters(w, ld)
    assert len(mons) == STOCKED
    assert all(mn.mdata is not None for mn in mons)
    assert all(mn.mdata.pmnames[2] == "leprechaun" for mn in mons)
    caps = _gold_budget(m, room, room.doors[0], ld)
    gold = {it.pos: it for it in _items(w, ld) if it.otyp == int(O.GOLD_PIECE)}
    assert len(gold) == STOCKED
    for pos, cap in caps.items():
        assert 10 <= gold[pos].quan <= cap + 9
    assert all(mn.sleeping == 1 for mn in mons)
    assert_item_locations(w)


# ------------------------------------------------------------
# MORGUE (C: fill_zoo case MORGUE + morguemon)
# ------------------------------------------------------------


def test_morgue_gets_corpses_chests_graves_and_undead():
    """PLAN-SPECIAL-ROOMS.md phase 2: the per-square rolls -- a corpse
    1 in 5, a chest or large box 1 in 10 ("lots of treasure buried
    with dead"), a grave 1 in 5 (the GRAVE terrain through
    make_grave) -- and one undead per square (at depth 5 the
    morguemon ladder is ghost / wraith / zombie; the demon and the
    vampire rungs need hd > 10 / > 8)."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.MORGUE, 5)
    mons = _monsters(w, 5)
    assert len(mons) == STOCKED
    assert all(mn.sleeping == 1 for mn in mons)
    assert all(mn.mdata is not None for mn in mons)
    assert all(mn.mdata.mlet in UNDEAD for mn in mons)
    items = _items(w, 5)
    assert any(it.otyp == int(O.CORPSE) for it in items)
    assert any(it.otyp in (int(O.CHEST), int(O.LARGE_BOX)) for it in items)
    graves = sum(
        1
        for y in range(H)
        for x in range(W)
        if m.tile_at((x, y)).typ == TerrainType.GRAVE
    )
    assert graves > 0
    assert m.flags.has_morgue
    assert_item_locations(w)


# ------------------------------------------------------------
# BEEHIVE (C: fill_zoo case BEEHIVE)
# ------------------------------------------------------------


def test_beehive_has_exactly_one_queen_at_the_centre():
    """C: the queen square is the room's centre (tx = lx +
    (hx - lx + 1) / 2, ty = ly + (hy - ly + 1) / 2), a killer bee on
    every other stocked square, royal jelly 1 in 3."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.BEEHIVE, 5)
    mons = _monsters(w, 5)
    assert len(mons) == STOCKED
    assert all(mn.sleeping == 1 for mn in mons)
    queen = w.monster_at_lev(5, CENTER)
    assert queen is not None
    assert queen.mdata is not None
    assert queen.mdata.pmnames[2] == "queen bee"
    killers = [mn for mn in mons if mn is not queen]
    assert all(mn.mdata is not None for mn in killers)
    assert all(mn.mdata.pmnames[2] == "killer bee" for mn in killers)
    assert any(it.otyp == int(O.LUMP_OF_ROYAL_JELLY) for it in _items(w, 5))
    assert m.flags.has_beehive
    assert_item_locations(w)


# ------------------------------------------------------------
# ANTHOLE (C: fill_zoo case ANTHOLE + antholemon)
# ------------------------------------------------------------


def test_anthole_is_single_species_with_food():
    """PLAN-SPECIAL-ROOMS.md phase 2: the ant species is the level's
    (birth % 3 + depth, draw-free -- the roll-side pre-check and the
    per-square calls agree for free), food 1 in 3, and C sets no
    level flag for the anthole (the flag switch has no case)."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.ANTHOLE, 5)
    mons = _monsters(w, 5)
    assert len(mons) == STOCKED
    # birth 0, depth 5: (0 + 5) % 3 == 2 -- the giant ant
    assert all(mn.mdata is not None for mn in mons)
    assert all(mn.mdata.pmnames[2] == "giant ant" for mn in mons)
    assert all(mn.sleeping == 1 for mn in mons)
    assert any(it.oclass == int(ObjClass.FOOD) for it in _items(w, 5))
    assert not m.flags.has_zoo
    assert_item_locations(w)


def test_antholemon_rotates_past_genocided_species():
    """C: the chosen species rotates (up to the other two) when
    genocided or extinct; all three gone answers None (C: NULL)."""
    m = blank_map(W, H)
    w = _world(m, 5)
    assert mkroom.antholemon(w).pmnames[2] == "giant ant"  # (0 + 5) % 3
    w.mon_state.mvitals[PM_GIANT_ANT].mvflags |= G_GONE
    assert mkroom.antholemon(w).pmnames[2] == "soldier ant"  # (5+1) % 3
    w.mon_state.mvitals[PM_SOLDIER_ANT].mvflags |= G_GONE
    assert mkroom.antholemon(w).pmnames[2] == "fire ant"  # (5+2) % 3
    w.mon_state.mvitals[PM_FIRE_ANT].mvflags |= G_GONE
    assert mkroom.antholemon(w) is None


# ------------------------------------------------------------
# BARRACKS / COCKNEST (C: fill_zoo case BARRACKS / COCKNEST)
# ------------------------------------------------------------


def test_barracks_gets_the_squad_and_the_payroll():
    """C: squadmon() per square over the squadprob[] table (soldier
    80 / sergeant 15 / lieutenant 4 / captain 1), a chest or large
    box 1 in 20 ("the payroll and some loot"), flags.has_barracks."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.BARRACKS, 5)
    mons = _monsters(w, 5)
    assert len(mons) == STOCKED
    assert all(mn.mdata is not None for mn in mons)
    squad = {"soldier", "sergeant", "lieutenant", "captain"}
    assert all(mn.mdata.pmnames[2] in squad for mn in mons)
    assert all(mn.sleeping == 1 for mn in mons)
    assert any(
        it.otyp in (int(O.CHEST), int(O.LARGE_BOX)) for it in _items(w, 5)
    )
    assert m.flags.has_barracks
    assert_item_locations(w)


def test_cocknest_gets_statues_with_loot():
    """C: a cockatrice per square; a statue 1 in 3, each stuffed with
    rn2(5) random objects (mkobj RANDOM_CLASS through
    add_to_container, the owt recount)."""
    m, room = _room_map()
    w = _claim_and_fill(m, room, RoomType.COCKNEST, 5)
    mons = _monsters(w, 5)
    assert len(mons) == STOCKED
    assert all(mn.mdata is not None for mn in mons)
    assert all(mn.mdata.pmnames[2] == "cockatrice" for mn in mons)
    statues = [it for it in _items(w, 5) if it.otyp == int(O.STATUE)]
    assert statues
    assert any(it.contents for it in statues)  # at least one is stuffed
    assert all(mn.sleeping == 1 for mn in mons)
    assert_item_locations(w)


# ------------------------------------------------------------
# fill_special_room (C: sp_lev.c 2732 -- the dispatcher)
# ------------------------------------------------------------


def test_fill_special_room_refuses_ordinary_and_unclaimed_rooms():
    """C: OROOM / THEMEROOM and needfill == FILL_NONE return before
    the stocking AND before the flag switch (no monsters, no flags)."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.fill_special_room(w, _rng(), m, [], room, 5)  # the OROOM
    assert not _monsters(w, 5)
    assert not m.flags.has_zoo
    room.rtype = RoomType.ZOO  # claimed, but needfill stays FILL_NONE
    mkroom.fill_special_room(w, _rng(), m, [], room, 5)
    assert not _monsters(w, 5)
    assert not m.flags.has_zoo


def test_vault_gets_gold_per_square_and_the_flag():
    """C: the VAULT branch -- every square of the room gets
    rn1(|lev| * 100, 51) gold (no monsters, no terrain change),
    flags.has_vault.  The branch makes the vault room type useful
    before vault.c's create_vault lands (the plan's phase 5)."""
    m, room = _room_map()
    lev = 3
    w = _world(m, lev)
    room.rtype = RoomType.VAULT
    room.needfill = FILL_NORMAL
    mkroom.fill_special_room(w, _rng(), m, [], room, lev)
    gold = [it for it in _items(w, lev) if it.otyp == int(O.GOLD_PIECE)]
    assert len(gold) == 70  # the whole floor rectangle, one pile each
    assert all(51 <= it.quan <= abs(lev) * 100 + 50 for it in gold)
    assert not _monsters(w, lev)
    assert m.flags.has_vault
    assert_item_locations(w)


# ------------------------------------------------------------
# mkundead (C: mkroom.c 455 -- the signature S32 got wrong)
# ------------------------------------------------------------


def test_mkundead_raises_a_swarm_and_sets_the_graveyard():
    """C: (level_difficulty() + 1) / 10 + rnd(5) undead (1..5 at
    depth 5), each a morguemon() on an enexto() square, and the
    level's graveyard flag ("reduced chance for undead corpse")."""
    m, room = _room_map()
    w = _world(m, 5)
    mkroom.mkundead(w, _rng(), m, 5, CENTER, False, NO_MM_FLAGS)
    mons = _monsters(w, 5)
    assert 1 <= len(mons) <= 5
    for mn in mons:
        assert mn.mdata is not None
        assert mn.mdata.mlet in UNDEAD
        # an enexto square: a king-move neighbour of the raise point
        assert max(abs(mn.pos[0] - CENTER[0]), abs(mn.pos[1] - CENTER[1])) == 1
    assert m.flags.graveyard
    assert_item_locations(w)


def test_mkundead_with_revive_skips_a_corpsed_square():
    """The unported revive() half (the docstring's named skip): a
    corpse on the target square counts as revived, so a corpse on
    every neighbour square means no new undead -- but the graveyard
    flag is still set (C sets it after the loop, unconditionally)."""
    m, room = _room_map()
    w = _world(m, 5)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                mksobj_at(
                    w, _rng(), int(O.CORPSE),
                    (CENTER[0] + dx, CENTER[1] + dy), 5,
                )
    mkroom.mkundead(w, _rng(), m, 5, CENTER, True, NO_MM_FLAGS)
    assert not _monsters(w, 5)
    assert m.flags.graveyard
    assert_item_locations(w)


# ------------------------------------------------------------
# the pickers (C: mkroom.c)
# ------------------------------------------------------------


def test_courtmon_ladder_tracks_depth():
    """C: i = rn2(60) + rn2(3 * depth).  At depth 5 (i <= 73) only
    the five low rungs are reachable, and every one of them is in the
    level's band (the orc / bugbear / hobgoblin / gnome / kobold rows
    are all difficulty <= 3, the band [0, 3]) -- the centaur and
    deeper rungs are above i's reach.  At depth 24 the band reaches
    the baby dragons (difficulty 12), so the dragon rung comes out
    (the low rungs' rows fall out of the band [4, 12] and answer
    None -- C's anymon fallback)."""
    w5 = _world(blank_map(W, H), 5)
    seen5 = set()
    for s in range(300):
        pm = mkroom.courtmon(w5, _rng(s))
        assert pm is not None
        seen5.add(pm.mlet)
    assert seen5 == {S_ORC, S_HUMANOID, S_GNOME, S_KOBOLD}
    w24 = _world(blank_map(W, H), 24)
    seen24 = set()
    for s in range(400):
        pm = mkroom.courtmon(w24, _rng(s))
        if pm is not None:
            seen24.add(pm.mlet)
    assert S_DRAGON in seen24
    assert seen24 <= {
        S_DRAGON,
        S_GIANT,
        S_TROLL,
        S_CENTAUR,
        S_ORC,
        S_HUMANOID,
        S_GNOME,
        S_KOBOLD,
    }


def test_squadmon_answers_the_squad_and_none_when_gone():
    """C: the walk over squadprob[] (the cumulative cpro > sel_prob
    test), and the G_GONE test answers NULL.  With all four squad
    types genocided that is the only answer."""
    m = blank_map(W, H)
    w = _world(m, 5)
    names = set()
    for s in range(100):
        pm = mkroom.squadmon(w, _rng(s))
        assert pm is not None
        names.add(pm.pmnames[2])
    assert names <= {"soldier", "sergeant", "lieutenant", "captain"}
    for mndx in (PM_SOLDIER, PM_SERGEANT, PM_LIEUTENANT, PM_CAPTAIN):
        w.mon_state.mvitals[mndx].mvflags |= G_GONE
    for s in range(50):
        assert mkroom.squadmon(w, _rng(s)) is None


# ------------------------------------------------------------
# the structural one (the plan)
# ------------------------------------------------------------


def test_the_room_stays_walkable_after_the_fill():
    """PLAN-SPECIAL-ROOMS.md phase 2: the fill adds monsters and
    objects (and the court's THRONE, the morgue's GRAVE) but the
    room's floor stays walkable terrain and the door stays a door."""
    for rtype in (RoomType.ZOO, RoomType.COURT, RoomType.MORGUE):
        m, room = _room_map()
        _claim_and_fill(m, room, rtype, 5)
        for sx in range(LX, HX + 1):
            for sy in range(LY, HY + 1):
                typ = m.tile_at((sx, sy)).typ
                assert typ in (
                    TerrainType.ROOM,
                    TerrainType.THRONE,
                    TerrainType.GRAVE,
                ), (rtype, sx, sy, typ)
        assert m.tile_at((LX, LY - 1)).typ == TerrainType.DOOR
