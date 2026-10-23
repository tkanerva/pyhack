"""Tests for the stairs system (PLAN-STAIRS.md §6).

House conventions: SeqRng for exact draws, conftest.make_world for
the tiny worlds, assert on the world state AND the event list; the
StairsCommand goes through step() where the wiring is the point.
"""
import random

from core import (MoveCommand, StairsCommand, WaitCommand, step)
from core.events import (GameOverEvent, LevelChangeEvent, MessageEvent,
                         TrapTriggeredEvent)
from core.rules import apply_stuck
from core.stairs import go_stairs, rebuild_stairs
from core.types import (Item, Monster, ObjectType, Pos, STAIR_DOWN,
                        STAIR_UP, Stairway, TerrainType, Tile, Trap, TrapType)
from core.worldgen import LEVEL1_DN_STAIRS, generate_level, new_world
from conftest import SeqRng, make_hero, make_map, make_world


# ------------------------------------------------------------
# worldgen plumbing
# ------------------------------------------------------------

def test_new_world_is_multi_level():
    w = new_world(random.Random(42), levels=3)
    assert w.lev == 1
    assert w.max_lev == 3
    assert w.levels == {}
    assert w.hero.pos == (20, 10)
    tile = w.map.tile_at(LEVEL1_DN_STAIRS)
    assert tile.typ == TerrainType.STAIRS
    assert tile.stair_dir == STAIR_DOWN
    # level 1: the single fixed down stairs, NO up stairs
    # (C: dlevel == 1 -> no upstairs)
    assert w.stairs == [Stairway(pos=LEVEL1_DN_STAIRS, up=False)]


def test_generate_level_deterministic_and_stairs():
    """Two same-seed descents produce the same level 2: same tiles,
    same stair positions (up + down, distinct), same trap / monster
    positions; the stair tiles are reserved from traps, monsters and
    items; no floor items on new levels."""
    def descend():
        w = new_world(random.Random(42), levels=3)
        w.hero.pos = LEVEL1_DN_STAIRS
        step(w, StairsCommand(up=False), random.Random(42))
        assert w.lev == 2
        tiles = [[(t.typ, t.stair_dir) for t in row] for row in w.map.tiles]
        up = [s.pos for s in w.stairs if s.up]
        dn = [s.pos for s in w.stairs if not s.up]
        traps = {t.id: (t.pos, t.trap_type) for t in w.traps.values()
                 if t.lev == 2}
        mons = {m.id: (m.pos, m.name) for m in w.actors.values()
                if not m.is_hero and m.lev == 2}
        items = [it.id for it in w.items.values()
                 if it.lev == 2 and it.pos is not None]
        return tiles, up, dn, traps, mons, items

    a = descend()
    b = descend()
    assert a == b
    tiles, up, dn, traps, mons, items = a
    # level 2 (neither level 1 nor the bottom) has BOTH stairs
    assert len(up) == 1 and len(dn) == 1 and up[0] != dn[0]
    for pos, want in ((up[0], STAIR_UP), (dn[0], STAIR_DOWN)):
        assert tiles[pos[1]][pos[0]] == (TerrainType.STAIRS, want)
    assert len(traps) == 10
    assert len(mons) == 9
    assert not any(pos in (up[0], dn[0]) for pos, _ in traps.values())
    assert not any(pos in (up[0], dn[0]) for pos, _ in mons.values())
    assert items == []


def test_bottom_level_has_up_stairs_only_and_victory():
    w = new_world(random.Random(42), levels=3)
    w.hero.pos = LEVEL1_DN_STAIRS
    step(w, StairsCommand(up=False), random.Random(42))  # -> level 2
    dn = next(s.pos for s in w.stairs if not s.up)
    w.hero.pos = dn
    ev = step(w, StairsCommand(up=False), random.Random(42))  # -> level 3
    assert w.lev == 3
    # the bottom level (C: Is_botlevel) has only the up stairs
    assert any(s.up for s in w.stairs)
    assert not any(not s.up for s in w.stairs)
    assert any(isinstance(e, LevelChangeEvent) and e.lev == 3
               and e.first_visit for e in ev)
    go = [e for e in ev if isinstance(e, GameOverEvent)]
    assert go and go[0].victory
    assert go[0].reason == "You have reached the bottom of the dungeon!"
    assert w.over
    # no further commands after the game is over
    assert step(w, StairsCommand(up=True), SeqRng()) == []


# ------------------------------------------------------------
# go_stairs / step (the command goes through step, not just direct
# calls -- the wiring is the point)
# ------------------------------------------------------------

def test_descend_and_climb_back():
    w = new_world(random.Random(42), levels=3)
    w.hero.pos = LEVEL1_DN_STAIRS
    ev = step(w, StairsCommand(up=False), random.Random(42))
    assert w.lev == 2
    assert w.hero.lev == 2
    # the hero arrives on the destination's UP stairs (C: u_on_upstairs)
    up = next(s.pos for s in w.stairs if s.up)
    assert w.hero.pos == up
    texts = [e.text for e in ev if isinstance(e, MessageEvent)]
    assert "You descend the stairs." in texts
    assert "You are now on level 2 of 3." in texts
    assert any(isinstance(e, LevelChangeEvent) and e.lev == 2
               and e.first_visit for e in ev)
    assert w.turn == 1
    # level 1 is parked with its monsters still there
    assert set(w.levels) == {1}
    assert sum(1 for m in w.actors.values()
               if not m.is_hero and m.lev == 1) == 9
    # climb back up from the up stairs
    ev = step(w, StairsCommand(up=True), random.Random(42))
    assert w.lev == 1
    assert w.hero.pos == LEVEL1_DN_STAIRS
    assert w.hero.lev == 1
    texts = [e.text for e in ev if isinstance(e, MessageEvent)]
    assert "You climb up the stairs." in texts
    # the return is not a first visit: no level-number line
    lvc = [e for e in ev if isinstance(e, LevelChangeEvent)]
    assert lvc == [LevelChangeEvent(lev=1, first_visit=False)]
    assert "You are now on level 1 of 3." not in texts
    # level 2 is parked now, its state intact
    assert set(w.levels) == {2}
    assert sum(1 for m in w.actors.values()
               if not m.is_hero and m.lev == 2) == 9


def _stair_world(hero_pos=(6, 4)):
    """A 12x8 all-floor world with a single down stair at (6, 3);
    max_lev 2 so a descent would generate."""
    m = make_map()
    m.tiles[3][6] = Tile(typ=TerrainType.STAIRS, stair_dir=STAIR_DOWN)
    w = make_world(map=m, hero=make_hero(pos=hero_pos))
    w.max_lev = 2
    rebuild_stairs(w)
    return w


def test_no_stairs_at_the_hero_tile_refuses():
    w = _stair_world()  # the hero at (6, 4), the stair at (6, 3)
    ev = step(w, StairsCommand(up=False), SeqRng())
    assert w.lev == 1
    assert w.hero.pos == (6, 4)
    assert w.levels == {}  # no level generated
    assert not any(isinstance(e, LevelChangeEvent) for e in ev)
    assert any(isinstance(e, MessageEvent)
               and e.text == "You can't go down here." for e in ev)
    ev = step(w, StairsCommand(up=True), SeqRng())
    assert w.lev == 1
    assert not any(isinstance(e, LevelChangeEvent) for e in ev)
    assert any(isinstance(e, MessageEvent)
               and e.text == "You can't go up here." for e in ev)


def test_up_on_the_level_one_down_stairs_refused():
    """Level 1 has no up stairs: '<' on the down stair refuses (C:
    doup on a stway with !stway->up)."""
    w = _stair_world(hero_pos=(6, 3))
    ev = step(w, StairsCommand(up=True), SeqRng())
    assert w.lev == 1
    assert w.levels == {}
    assert not any(isinstance(e, LevelChangeEvent) for e in ev)
    assert any(isinstance(e, MessageEvent)
               and e.text == "You can't go up here." for e in ev)


def test_down_on_the_bottom_level_refused():
    w = _stair_world(hero_pos=(6, 3))
    w.lev = 2  # the bottom (max_lev is 2)
    w.hero.lev = 2
    ev = step(w, StairsCommand(up=False), SeqRng())
    assert w.lev == 2
    assert w.levels == {}
    assert not any(isinstance(e, LevelChangeEvent) for e in ev)
    assert any(isinstance(e, MessageEvent)
               and e.text == "You can't go down here." for e in ev)


def test_stuck_hero_cannot_use_the_stairs():
    w = _stair_world(hero_pos=(6, 3))
    apply_stuck(w, "player", 10, message=False)
    ev = step(w, StairsCommand(up=False), SeqRng())
    assert w.lev == 1
    assert w.levels == {}
    assert not any(isinstance(e, LevelChangeEvent) for e in ev)
    assert any(isinstance(e, MessageEvent)
               and e.text == "You are stuck and can't use the stairs."
               for e in ev)


def test_asleep_hero_ignores_the_stairs_command():
    w = _stair_world(hero_pos=(6, 3))
    w.hero.sleeping = 1
    ev = step(w, StairsCommand(up=False), SeqRng())
    assert w.lev == 1
    assert w.levels == {}
    assert not any(isinstance(e, LevelChangeEvent) for e in ev)


# ------------------------------------------------------------
# the arrival collision (C: u_collide_m) -- go_stairs direct, with
# a pre-parked level 2 so the descent draws only the collision roll
# ------------------------------------------------------------

def _stair_pos(m, want_dir) -> Pos:
    for y in range(m.height):
        for x in range(m.width):
            t = m.tiles[y][x]
            if t.typ == TerrainType.STAIRS and t.stair_dir == want_dir:
                return (x, y)
    raise AssertionError("no stair of the wanted direction")


def _free_adjacent(m, pos: Pos):
    out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            p = (pos[0] + dx, pos[1] + dy)
            if m.in_bounds(p) and m.is_walkable(p):
                out.append(p)
    return out


def _world_on_the_level1_stairs(monster_on_arrival: bool):
    w = new_world(random.Random(42), levels=3)
    w.hero.pos = LEVEL1_DN_STAIRS
    m2 = generate_level(w, 2, random.Random(1234))
    w.levels[2] = m2  # parked: the descent below draws nothing
    up_pos = _stair_pos(m2, STAIR_UP)
    if monster_on_arrival:
        w.actors["goblin_l2"] = Monster(
            id="goblin_l2", name="Goblin", pos=up_pos, hp=8, max_hp=8,
            ac=7, lev=2)
    return w, m2, up_pos


def test_arrival_collision_even_moves_the_hero():
    """SeqRng(2, ...) pins the rn2-style draw even: the hero steps to
    the (preset) adjacent tile, the monster stays on the stairs."""
    w, m2, up_pos = _world_on_the_level1_stairs(True)
    p = _free_adjacent(m2, up_pos)[0]
    mon = w.actors["goblin_l2"]
    ev = go_stairs(w, False, SeqRng(2, p))
    assert w.lev == 2
    assert w.hero.pos == p
    assert mon.pos == up_pos
    assert mon.alive
    assert any(isinstance(e, MessageEvent)
               and e.text == "You descend the stairs." for e in ev)


def test_arrival_collision_odd_moves_the_monster():
    """SeqRng(1, ...) pins the draw odd: the monster is moved to the
    (preset) adjacent tile, the hero keeps the stairs."""
    w, m2, up_pos = _world_on_the_level1_stairs(True)
    p = _free_adjacent(m2, up_pos)[0]
    mon = w.actors["goblin_l2"]
    ev = go_stairs(w, False, SeqRng(1, p))
    assert w.lev == 2
    assert w.hero.pos == up_pos
    assert mon.pos == p
    assert mon.alive
    assert any(isinstance(e, MessageEvent)
               and e.text == "You descend the stairs." for e in ev)


# ------------------------------------------------------------
# cross-level isolation
# ------------------------------------------------------------

def test_cross_level_isolation():
    """On level 2: a wait does not tick / move level-1 monsters, and
    a level-1 actor is never returned from monster_at (decision 3)."""
    w = new_world(random.Random(42), levels=3)
    w.hero.pos = LEVEL1_DN_STAIRS
    step(w, StairsCommand(up=False), random.Random(42))
    assert w.lev == 2
    l1 = [(m.id, m.pos, m.stuck, m.sleeping) for m in w.actors.values()
          if not m.is_hero and m.lev == 1]
    assert len(l1) == 9
    for m in (m for m in w.actors.values()
              if not m.is_hero and m.lev == 1):
        found = w.monster_at(m.pos)
        # a level-2 monster may share the coordinate, never the actor
        assert found is None or found.lev == 2
    step(w, WaitCommand(), random.Random(42))
    l1_after = [(m.id, m.pos, m.stuck, m.sleeping)
                for m in w.actors.values()
                if not m.is_hero and m.lev == 1]
    assert l1_after == l1


def test_traps_and_items_filtered_by_level():
    """A level-1 trap / item at (7,4) is invisible from level 2 (no
    trigger, not in items_at) and live again after returning."""
    m1 = make_map()
    m1.tiles[3][6] = Tile(typ=TerrainType.STAIRS, stair_dir=STAIR_DOWN)
    it = Item(id="armor_1", otype=ObjectType.ARMOR, name="leather armor",
              pos=(7, 4), lev=1)
    w = make_world(map=m1, hero=make_hero(pos=(6, 3)),
                   traps=[Trap(id="trap_l1", trap_type=TrapType.PIT,
                               pos=(7, 4), lev=1)],
                   items=[it])
    w.max_lev = 2
    rebuild_stairs(w)
    assert w.items_at((7, 4)) == [it]
    # onto level 2 (a plain floor map, parked by hand)
    m2 = make_map()
    w.levels[2] = m2
    w.map = m2
    w.lev = 2
    w.hero.lev = 2
    rebuild_stairs(w)
    assert w.items_at((7, 4)) == []
    # standing on the level-1 trap's coordinates: no trigger, no roll
    w.hero.pos = (6, 4)
    ev = step(w, MoveCommand(1, 0), SeqRng())
    assert w.hero.pos == (7, 4)
    assert not w.traps["trap_l1"].triggered
    assert not any(isinstance(e, TrapTriggeredEvent) for e in ev)
    # back on level 1: the same tile DOES trigger (the rolls are pinned)
    w.levels[2] = w.map
    w.map = m1
    w.lev = 1
    w.hero.lev = 1
    w.hero.pos = (6, 4)
    rebuild_stairs(w)
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 3))  # 1 <= 30; pit 1d6=3
    assert w.hero.pos == (7, 4)
    assert w.traps["trap_l1"].triggered
    assert any(isinstance(e, TrapTriggeredEvent) for e in ev)
    assert w.items_at((7, 4)) == [it]


# ------------------------------------------------------------
# integration: the whole game with the stairs
# ------------------------------------------------------------

def test_full_game_with_stairs_is_deterministic():
    """Same seed + same commands => the same game, including the lazy
    level-2 generation on the shared rng stream (the test_demo
    pattern, extended with the stairs)."""
    def play():
        rng = random.Random(42)
        w = new_world(rng, levels=3)
        out = []
        cmds = ([MoveCommand(0, -1)] * 8 + [StairsCommand(up=False)]
                + [MoveCommand(1, 0), MoveCommand(0, 1), WaitCommand()]
                + [StairsCommand(up=True)] + [WaitCommand()])
        for cmd in cmds:
            out.extend(step(w, cmd, rng))
        return (w.lev, w.hero.pos, w.turn,
                {m.id: (m.hp, m.pos, m.alive, m.lev)
                 for m in w.actors.values()},
                [repr(e) for e in out])

    assert play() == play()
