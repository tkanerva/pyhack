"""The stairs system: the multi-level dungeon, go down with '>' and
up with '<' (C: the cmd.c entries for '>' / '<' -> dodown() / doup()).

Port of the NetHack 5.0 C stairs (demo subset; the design and the
documented simplifications are PLAN-STAIRS.md):
  src/stairs.c   the stairway list (world.stairs, C: gs.stairs) + the
                 u_on_* placement helpers
  src/do.c       dodown() / doup() -> go_stairs(), the transition
                 goto_level(), the arrival collision u_collide_m()
  src/dungeon.c  next_level() / prev_level() -- the demo derives the
                 destination as world.lev +/- 1 (C: stway->tolev)
  src/mklev.c    mkstairs() / generate_stairs() -- the stair half
                 lives in core.worldgen.generate_level

Stairs are TERRAIN (Tile.typ == STAIRS + Tile.stair_dir, C:
levl[x][y].typ == STAIRS + the levl[x][y].ladder LA_UP/LA_DOWN mask)
plus per-level STAIRWAY RECORDS (world.stairs), rebuilt on every
level entry (rebuild_stairs scans the map's STAIRS tiles -- the demo
equivalent of the stairway_add calls in mkstairs / restore.c, after
the stairway_free_all of goto_level).  Levels are generated on first
visit (worldgen.generate_level, C: mklev()) and kept in memory
afterwards (world.levels, the getlev() equivalent: "coming back up"
restores everything exactly).
"""
from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

from .events import Event, GameOverEvent, LevelChangeEvent, MessageEvent
from .hacklib import is_stuck
from .types import (Monster, Pos, STAIR_UP, Stairway, TerrainType, World)
from .vision import vision_recalc, vision_reset


def rebuild_stairs(world: World) -> None:
    """Rebuild world.stairs from the current level's STAIRS tiles.

    C: the gs.stairs list holds only the current level's stairways --
    stairway_free_all() in goto_level, re-added by the stairway_add
    calls of mkstairs (new level) / getlev's restore (old level).
    The demo rebuilds it by scanning the map (the stair_dir carries
    the up/down half of the C record).
    """
    stairs: List[Stairway] = []
    for y in range(world.map.height):
        for x in range(world.map.width):
            tile = world.map.tiles[y][x]
            if tile.typ == TerrainType.STAIRS:
                stairs.append(Stairway(pos=(x, y),
                                       up=tile.stair_dir == STAIR_UP))
    world.stairs = stairs


def _stairway_at(world: World, pos: Pos) -> Optional[Stairway]:
    """C: stairway_at -- the staircase under the hero, if any."""
    for s in world.stairs:
        if s.pos == pos:
            return s
    return None


def _monster_at(world: World, pos: Pos) -> Optional[Monster]:
    """The live NON-hero monster on `pos` on the current level.

    C: m_at -- the hero is not in the monster list, so at the hero's
    own tile World.monster_at (an actor scan) cannot be used.
    """
    for m in world.actors.values():
        if (m.alive and not m.is_hero and m.lev == world.lev
                and m.pos == pos):
            return m
    return None


def _free_adjacent(world: World, pos: Pos) -> List[Pos]:
    """Walkable, unoccupied tiles on the Chebyshev-1 ring of `pos`
    (C: enexto / mnexto; the demo ring -- C's mnexto searches a wider
    ring, PLAN-STAIRS.md §4)."""
    opts: List[Pos] = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            p = (pos[0] + dx, pos[1] + dy)
            if world.map.is_walkable(p) and _monster_at(world, p) is None:
                opts.append(p)
    return opts


def _u_collide_m(world: World, mon: Monster, rng) -> None:
    """C: do.c u_collide_m -- a monster shares the hero's arrival
    spot.  50/50 (C: rn2(2), demo: rng.randint(1, 2)): even -> move
    the hero to a random free adjacent tile (C: enexto + next2u),
    odd -> move the monster to a random free adjacent tile (C:
    mnexto, the demo ring).  If the monster still shares the tile
    after the move it is dropped (C: rloc then m_into_limbo; the
    demo has no limbo -- alive=False, no message, PLAN-STAIRS.md §4).
    """
    moved = False
    if rng.randint(1, 2) % 2 == 0:
        opts = _free_adjacent(world, world.hero.pos)
        if opts:
            world.hero.pos = rng.choice(opts)
            moved = True
    if not moved:
        opts = _free_adjacent(world, mon.pos)
        if opts:
            mon.pos = rng.choice(opts)
    if _monster_at(world, world.hero.pos) is not None:
        mon.alive = False


def goto_level(world: World, target_lev: int, at_stairs: bool,
               rng) -> List[Event]:
    """C: do.c goto_level (demo subset) -- the level transition.

    Order mirrors C: (1) the on_level / range guard, (2) save the
    old level (park it in world.levels -- C's savelev writes the
    level file; the demo keeps the object), (3) first visit ->
    generate (C: mklev()) else take the parked map back (C:
    getlev()), (4) set the level + rebuild the stairways (C:
    stairway_free_all + re-add), (5) hero placement on the matching
    staircase (C: u_on_dnstairs when going up, u_on_upstairs when
    going down -- the stairs back toward the level you came from),
    (6) the arrival collision (C: u_collide_m), (7) the vision
    reset + recalc (C: vision_reset + docrt), (8) the events
    (LevelChangeEvent + the C message lines, verbatim).

    Everything else in the C goto_level (endgame / quest / knox
    branches, the mysterious force, regions, timers, migration,
    shops, fall damage, auto-pickup) is out of scope
    (PLAN-STAIRS.md §4/§5).
    """
    events: List[Event] = []
    # C: if (on_level(newlevel, &u.uz)) return; the stair checks of
    # go_stairs keep the destination in range -- this is the belt
    if not 1 <= target_lev <= world.max_lev or target_lev == world.lev:
        return events

    # local import: core.worldgen imports this module (rebuild_stairs)
    from .worldgen import generate_level

    old_lev = world.lev
    up = target_lev < old_lev
    world.levels[old_lev] = world.map  # C: savelev
    first_visit = target_lev not in world.levels
    m = world.levels.get(target_lev)
    if m is None:
        m = generate_level(world, target_lev, rng)  # C: mklev()
    else:
        del world.levels[target_lev]                # C: getlev()
    world.map = m

    world.lev = target_lev
    world.hero.lev = target_lev
    rebuild_stairs(world)

    if at_stairs:
        # C: u_on_dnstairs (going up) / u_on_upstairs (going down) --
        # the destination's staircase back toward the level you came
        # from.  The matching stair always exists in the main dungeon
        # (the C stairway_find_from reverse lookup is unneeded,
        # PLAN-STAIRS.md §2.4).
        want_up = not up
        stair = next((s for s in world.stairs if s.up == want_up), None)
        assert stair is not None, "no matching staircase on the new level"
        world.hero.pos = stair.pos
        world.stairs = [replace(s, traversed=True) if s is stair else s
                        for s in world.stairs]  # C: u_traversed

    # C: if ((mtmp = m_at(u.ux, u.uy)) != 0) u_collide_m(mtmp);
    mon = _monster_at(world, world.hero.pos)
    if mon is not None:
        _u_collide_m(world, mon, rng)

    # C: vision_reset() + docrt() (the full recalc)
    vision_reset(world)
    vision_recalc(world)

    events.append(LevelChangeEvent(lev=target_lev, first_visit=first_visit))
    # the C message lines, verbatim (the demo log keeps them plain)
    events.append(MessageEvent("You climb up the stairs." if up
                               else "You descend the stairs."))
    if first_visit:
        events.append(MessageEvent(
            f"You are now on level {target_lev} of {world.max_lev}."))
    # the demo's goal: the bottom level is the win (decision 4.8)
    if target_lev == world.max_lev:
        world.over = True
        events.append(GameOverEvent(
            victory=True, reason="You have reached the bottom of the "
                                 "dungeon!"))
    return events


def go_stairs(world: World, up: bool, rng) -> List[Event]:
    """C: do.c dodown() (up=False, the '>' command) / doup()
    (up=True, the '<' command) -- the demo subset: the stair lookup
    + the refusals, then the transition.

    A refused stair command still consumes a turn (house rule:
    step() always advances the turn -- C distinguishes ECMD_OK from
    ECMD_TIME, pyhack does not, same as the scroll port).
    """
    hero = world.hero
    stair = _stairway_at(world, hero.pos)
    # C: doup refuses on !stway || !stway->up; dodown's plain refusal
    # (the hole / trap door / autodig branches are dropped, §4)
    if up:
        if stair is None or not stair.up:
            return [MessageEvent("You can't go up here.")]
    else:
        if stair is None or stair.up:
            return [MessageEvent("You can't go down here.")]
    # C: u_stuck_cannot_go
    if is_stuck(hero):
        return [MessageEvent("You are stuck and can't use the stairs.")]
    # C: next_level / prev_level -- in the main dungeon the
    # destination is lev +/- 1 (C: stway->tolev)
    target = world.lev - 1 if up else world.lev + 1
    if not 1 <= target <= world.max_lev:
        # C: the bottom level has no down stairs and level 1 no up
        # stairs, so the lookup above already refuses in the main
        # dungeon; this keeps the guard total for constructed worlds
        return [MessageEvent("You can't go up here." if up
                             else "You can't go down here.")]
    return goto_level(world, target, True, rng)
