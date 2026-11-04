"""Doors: open and close.

The door *terrain* comes from the level generator (core.mklev dosdoor):
a DOOR tile with a DoorMask, or a SDOOR tile that is still part of the
wall until it is found.  This module is the interaction half -- the two
things a hero can do to a door.

C provenance:

  src/lock.c  doopen() / doopen_indir()  (the 'o' command *and* the
              walk-into-a-closed-door case of hack.c's domove(), which
              is where pyhack opens doors -- see core.step._do_move)
  src/lock.c  doclose()                  (the 'c' command; 'x' here,
              because the console front-end already spends 'c' on
              casting)
  src/rm.h    closed_door() -- the "D_CLOSED only" test that makes a
              *locked* door answer with "This door is locked." instead
              of trying to open it

Included (the whole of both commands, minus the inventory):

  - the four refusals of doopen(): no door / broken / no door in the
    doorway / already open / locked, in C's order and wording;
  - the strength roll (C: rnl(20) < (STR + DEX + CON) / 3) and "The
    door resists!";
  - the trapped-door outcome (the door is destroyed and becomes a bare
    doorway);
  - close: the obstructed-doorway refusal, "already closed" / "broken",
    the strength roll (C: rn2(25) < (STR + DEX + CON) / 3) and the
    vision update both ways.

STUBs:

  - C's `b_trapped("door", FINGER)` -- the door trap's own explosion /
    damage, which belongs to trap.c's chest-and-door trap machinery;
    pyhack destroys the door and says so.
  - the autounlock follow-ups of doopen() (apply a key, offer to kick),
    the "you have no hands" polymorph check, stumbling on a door mimic,
    the drawbridge/portcullis branches and the shop damage billing.

Simplifications (documented, not bugs):

  - only the hero opens and closes doors.  Monsters need mmove()
    (monmove.c), which is not ported; that is also why a monster will
    path around a closed door rather than open it.
  - opening a door costs the turn even when it fails (pyhack has no
    ECMD_OK / ECMD_TIME distinction -- the same house rule as the
    stairs and scroll ports).
"""

from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .types import DoorMask, Monster, Pos, TerrainType, World, is_door
from .vision import recalc_block_point


def closed_door(world: World, pos: Pos) -> bool:
    """C: rm.h#closed_door -- a real door that is *closed* (a locked or
    trapped door is a different answer: "This door is locked.")."""
    if not world.map.in_bounds(pos):
        return False
    tile = world.map.tile_at(pos)
    return is_door(tile.typ) and bool(tile.door_mask & DoorMask.CLOSED)


def open_door(world: World, pos: Pos, rng) -> List[Event]:
    """C: lock.c#doopen_indir -- the hero tries to open the door at
    `pos`.  Returns the message events; the terrain change (and the
    vision update) is applied here.

    The C function returns ECMD_TIME for both outcomes (a resisting
    door also costs the turn), which the caller gets for free: pyhack
    always advances the turn.
    """
    hero = world.hero
    if not world.map.in_bounds(pos):
        return [MessageEvent("You see no door there.")]
    tile = world.map.tile_at(pos)
    if not is_door(tile.typ):
        return [MessageEvent("You see no door there.")]
    if not tile.door_mask & DoorMask.CLOSED:
        # C: not (D_CLOSED) -- broken / bare doorway / open / locked
        if tile.door_mask & DoorMask.BROKEN:
            return [MessageEvent("This door is broken.")]
        if not tile.door_mask:
            return [MessageEvent("This doorway has no door.")]
        if tile.door_mask & DoorMask.ISOPEN:
            return [MessageEvent("This door is already open.")]
        return [MessageEvent("This door is locked.")]
    # C: rnl(20) < (STR + DEX + CON) / 3 -- the CURR stats
    if rng.rnl(20, 0) < (hero.ustr + hero.udex + hero.ucon) // 3:
        events: List[Event] = [MessageEvent("The door opens.")]
        if tile.door_mask & DoorMask.TRAPPED:
            # C: b_trapped("door", FINGER) -- trap.c's door trap
            events.append(MessageEvent("A trap on the door goes off!"))
            tile.door_mask = DoorMask(0)  # D_NODOOR: blown away
        else:
            tile.door_mask = DoorMask.ISOPEN
        recalc_block_point(world, pos)
        return events
    events = [MessageEvent("The door resists!")]
    return events


def close_door(world: World, pos: Pos, rng) -> List[Event]:
    """C: lock.c#doclose -- the hero tries to close the door at `pos`.

    The refusals come in C's order (no door / bare doorway / something
    in the way / broken / already closed), then the strength roll and
    the vision update.
    """
    if not world.map.in_bounds(pos):
        return [MessageEvent("You see no door there.")]
    tile = world.map.tile_at(pos)
    if not is_door(tile.typ):
        return [MessageEvent("You see no door there.")]
    if not tile.door_mask:
        return [MessageEvent("This doorway has no door.")]
    blocker = _monster_at(world, pos)
    if blocker is not None:
        return [MessageEvent(f"{blocker.name} blocks the way!")]
    if tile.door_mask & DoorMask.BROKEN:
        return [MessageEvent("This door is broken.")]
    if tile.door_mask & (DoorMask.CLOSED | DoorMask.LOCKED):
        return [MessageEvent("This door is already closed.")]
    if tile.door_mask & DoorMask.ISOPEN:
        hero = world.hero
        if rng.rn2(25) < (hero.ustr + hero.udex + hero.ucon) // 3:
            tile.door_mask = DoorMask.CLOSED
            recalc_block_point(world, pos)
            return [MessageEvent("The door closes.")]
        return [MessageEvent("The door resists!")]
    return [MessageEvent("This door cannot be closed.")]


def _monster_at(world: World, pos: Pos) -> Optional[Monster]:
    """The live non-hero monster standing in a doorway (C: m_at)."""
    for mon in world.actors.values():
        if (mon.alive and not mon.is_hero and mon.lev == world.lev
                and mon.pos == pos):
            return mon
    return None


def is_doorway(world: World, pos: Pos) -> bool:
    """A square whose terrain is a door (the display / travel helpers
    want this without importing core.mklev)."""
    return world.map.in_bounds(pos) and \
        world.map.tile_at(pos).typ == TerrainType.DOOR


__all__ = ["close_door", "closed_door", "is_doorway", "open_door"]
