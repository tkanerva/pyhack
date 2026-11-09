"""The priest system (port of the src/priest.c subset).

A temple in pyhack is what PLAN-SPECIAL-ROOMS.md phase 1 says it is:
an ALTAR tile with an alignment mask (``Tile.altarmask``), a peaceful
priest who knows the room (the ``Epri`` extra, C: ``mextra->epri``)
standing next to it, the entry message (``intemple``), and the
``#pray`` / ``#offer`` refusal.  The prayer system itself -- sacrifice,
donation, altar wrath, the priest_talk() service economy -- is NOT
ported (src/pray.c is 2,721 lines; the plan says so loudly, §2.6):
every entry point into it refuses with C's own misaligned-altar line.

C provenance (the spans this module owns):

  src/priest.c   newepri() (the MM_EPRI allocation, in core.makemon),
                 priestini(), has_shrine(), histemple_at(),
                 findpriest(), intemple() (the reduced port),
                 dopray() / doffer() (the refusals)
  src/dungeon.c  induced_align() (the temple is its only live caller;
                 pyhack has no dungeon module, so it lives here)
  src/sp_lev.c   pm_good_location() (the ring test of priestini)
  src/decl.c     the xdir[] / ydir[] direction tables

The room itself (the room pick, the shrine square, the altar write,
the AM_SHRINE bit, the level flag) is core.mkroom.mktemple, which
calls priestini() the way C's mktemple() calls it.

What is deliberately thin (each named, PLAN-SPECIAL-ROOMS.md §5):

  - the intemple() message pacing (the epri timers: intone_time /
    enter_time / hostile_time / peaceful_time) is carried but never
    ticked -- the entry hook in core.step fires this function once per
    room crossing, which is what keeps the messages from repeating;
  - the intone() passage and the Sanctum / Moloch halves of
    intemple() (no special levels, no endgame);
  - the alignment record in the peace / forbidding test (C's
    ``u.ualign.record``: it starts at 0 and never trips either half);
  - the untended ghost's nomul(-3) "frightened to death" (pyhack has
    no stun occupation yet);
  - the priest's robe (C: the m_initweap / which_armor(W_ARMC) tail of
    priestini) waits for PLAN-MAKEMON.md phase E, so its rn2(2) roll
    is not taken; the 2-4 spellbooks are real (mkobj's
    SPBOOK_no_NOVEL + the addinv single writer);
  - mon_learns_traps() (C: the priest knows all traps) -- pyhack
    monsters have no per-monster trap knowledge.
"""

from __future__ import annotations

from typing import List, Optional

from . import mkobj
from .events import Event, MessageEvent
from .invent import addinv
from .makemon import makemon, set_malign
from .monst import MONS, PM_ALIGNED_CLERIC, PM_GHOST, PM_HIGH_CLERIC
from .monst_defs import AM_SHRINE, align2amask, amask2align
from .place import enexto
from .types import (
    MmFlags,
    Map,
    Monster,
    Pos,
    Room,
    RoomType,
    TerrainType,
    World,
    space_pos,
)
from .vision import can_see

# C: decl.c -- the direction tables priestini's ring search walks, in
# C order (W, NW, N, NE, E, SE, S, SW); N_DIRS is the 8-way subset of
# C's 10-way table (the two extra rows are the zdir vertical specials).
N_DIRS = 8
_XDIR = (-1, -1, 0, 1, 1, 1, 0, -1)
_YDIR = (0, -1, -1, -1, 0, 1, 1, 1)


# ============================================================
# The shrine's alignment (C: dungeon.c induced_align)
# ============================================================


def induced_align(rng) -> int:
    """C: dungeon.c#induced_align -- the alignment mask a new shrine
    answers to (the C return value is already an AM_* mask, not an
    aligntyp).

    C asks the special level's alignment first (``pct`` chance), then
    the dungeon's (``pct`` chance), and falls to the three-way roll
    (chaotic / neutral / lawful) when neither has one.  pyhack has no
    special levels and no dungeon topology (PLAN-SPLEV.md), so both
    flags are 0 and the answer is always the temperate-dungeon roll,
    masked: ``rn2(3) - 1`` -> ``align2amask`` (one draw, C's two
    rn2(100) level/dungeon tests short-circuit on the zero flags).
    """
    return align2amask(rng.rn2(3) - 1)


# ============================================================
# The priest (C: priest.c priestini and the shrine queries)
# ============================================================


def _pm_good_location(map_: Map, pos: Pos) -> bool:
    """C: sp_lev.c#pm_good_location (is_ok_location, DRY) -- a square
    the priest may stand on.

    The reduced test: in bounds and ``SPACE_POS`` (C's DRY half --
    floor, corridor, and, faithfully, the furniture and stairs that
    can sit next to the shrine), with no boulder (nothing places one
    yet, see core.place).  C's water / lava / solid halves need a
    species humidity the clerics do not have (pm_to_humidity is DRY).
    """
    if not map_.in_bounds(pos):
        return False
    return space_pos(map_.tile_at(pos).typ)


def priestini(
    world: World, map_: Map, room: Room, pos: Pos, sanctum: bool, lev: int, rng
) -> Optional[Monster]:
    """C: priest.c#priestini -- the priest of the temple: a cleric
    standing next to the shrine at `pos` in `room`.  `sanctum` makes
    the high priest (PM_HIGH_CLERIC); no sanctum level exists in
    pyhack, so the parameter keeps C's shape and the mktemple()
    caller passes False.

    The square search is C's: a 1-square ring around the shrine in
    C's direction order, starting at a random direction (``si =
    rn2(N_DIRS)``), the first square that passes pm_good_location;
    when the whole ring fails, the shrine square itself.  A monster
    already on the chosen square is relocated first (C's rloc()
    insurance), and a species that cannot be made at all answers None
    (C's NULL) -- a genocided cleric, a square nobody can share.

    `map_` / `lev` are the level being stocked: a lazily generated
    level is built while the hero still stands on the previous one
    (PLAN-MKLEV.md decision 3), and in_mklev=True marks the priest as
    part of the new level (C: gi.in_mklev).
    """
    prim = MONS[PM_HIGH_CLERIC if sanctum else PM_ALIGNED_CLERIC]
    assert prim is not None

    si = rng.rn2(N_DIRS)
    px = py = 0
    for i in range(N_DIRS):
        px = pos[0] + _XDIR[(i + si) % N_DIRS]
        py = pos[1] + _YDIR[(i + si) % N_DIRS]
        if _pm_good_location(map_, (px, py)):
            break
    else:
        px, py = pos  # C: if (i == N_DIRS) px = sx, py = sy;

    occupant = world.monster_at_lev(lev, (px, py))
    if occupant is not None:
        # C: rloc(m_at(px, py), RLOC_NOMSG) -- insurance
        spot = enexto(world, rng, map_, lev, (px, py), occupant.mdata)
        if spot is not None:
            occupant.pos = spot

    priest = makemon(
        world, rng, prim, (px, py), MmFlags.EPRI, map_=map_, lev=lev, in_mklev=True
    )
    if priest is None:
        return None
    epri = priest.epri
    assert epri is not None  # the MM_EPRI above allocated it
    epri.shroom = map_.room_of(room)
    # C reads the mask before mktemple() sets AM_SHRINE; amask2align
    # masks with AM_MASK either way
    epri.shralign = amask2align(map_.tile_at(pos).altarmask)
    epri.shrpos = pos
    epri.shrlevel = lev
    # C: mon_learns_traps(priest, ALL_TRAPS) -- no per-monster trap
    # knowledge in pyhack (the C call is named, not ported)
    priest.mpeaceful = True
    priest.ispriest = True
    priest.sleeping = 0
    set_malign(world, priest)  # C: mpeaceful may have changed

    # the goodies (C: the priestini tail): 2 to 4 spellbooks
    # (rn1(3, 2)); the robe half (m_initweap / which_armor W_ARMC and
    # its rn2(2) bless/curse) waits for PLAN-MAKEMON.md phase E
    for _ in range(rng.rn1(3, 2)):
        addinv(world, priest.id, mkobj.mkobj(world, rng, mkobj.SPBOOK_no_NOVEL))
    return priest


def has_shrine(priest: Monster, map_: Map) -> bool:
    """C: priest.c#has_shrine -- the priest's temple still contains a
    properly aligned altar (the test behind "a desecrated place")."""
    epri = priest.epri
    if epri is None or not priest.ispriest:
        return False
    tile = map_.tile_at(epri.shrpos)
    if tile.typ != TerrainType.ALTAR or not (tile.altarmask & AM_SHRINE):
        return False
    return epri.shralign == amask2align(tile.altarmask & ~AM_SHRINE)


def _histemple_at(world: World, priest: Monster, pos: Pos) -> bool:
    """C: priest.c#histemple_at -- the priest is in its own temple
    room, on the shrine's level (C: ``EPRI(priest)->shroom ==
    *in_rooms(x, y, TEMPLE)`` + on_level(shrlevel))."""
    epri = priest.epri
    if epri is None or not priest.ispriest:
        return False
    if priest.lev != epri.shrlevel:
        return False
    room = world.map.room_at(pos)
    return (
        room is not None
        and room.rtype == RoomType.TEMPLE
        and epri.shroom == world.map.room_of(room)
    )


def findpriest(world: World, lev: int, roomno: int) -> Optional[Monster]:
    """C: priest.c#findpriest -- the priest tending the temple with
    room number `roomno` on level `lev` (or None: the temple is
    untended).  C walks the level's own monster list; here the flat
    world list is filtered by level, which is the same read."""
    for mon in world.actors.values():
        if (
            mon.ispriest
            and mon.epri is not None
            and mon.epri.shroom == roomno
            and mon.lev == lev
            and _histemple_at(world, mon, mon.pos)
        ):
            return mon
    return None


def intemple(world: World, room: Room, rng) -> List[Event]:
    """C: priest.c#intemple -- the temple-entry message, reduced to
    the entry / peace / eerie half (PLAN-SPECIAL-ROOMS.md phase 1.5).

    A tended temple greets the pilgrim ("Pilgrim, you enter a sacred
    place!", or desecrated when the shrine is gone) and gives the
    peace / forbidding feeling from the altar's alignment and the
    hero's; an untended one gives the C eerie message and, 1 in 5, a
    ghost that appears next to the hero and turns hostile.  The C
    message pacing (the epri timers), the intone() passage, the
    alignment record and the Sanctum half are the named non-ports
    (module docstring); the room-entry hook in core.step fires this
    once per room crossing, which is what stands in for the pacing.
    """
    map_ = world.map
    events: List[Event] = []
    priest = findpriest(world, world.lev, map_.room_of(room))
    if priest is not None:
        epri = priest.epri
        assert epri is not None
        shrined = has_shrine(priest, map_)
        events.append(
            MessageEvent(
                f"Pilgrim, you enter a "
                f"{'sacred' if shrined else 'desecrated'} place!"
            )
        )
        if shrined and world.hero_align == epri.shralign:
            # C: `svm.moves >= peaceful_time` and the ALGN_DEVOUT
            # "a" / "an unusual" split -- the record half never trips
            # (it starts at 0), so the "unusual" article stands
            events.append(MessageEvent("You experience an unusual sense of peace."))
        else:
            # C: `!shrined || !p_coaligned(priest) || record <=
            # ALGN_SINNED` -- the record half waits for the alignment
            # system (it is 0 here, which never trips the test)
            events.append(MessageEvent("You have a forbidding feeling..."))
    else:
        # untended (C: the rn2(4) switch, then the 1-in-5 ghost)
        roll = rng.rn2(4)
        if roll == 0:
            events.append(MessageEvent("You have an eerie feeling..."))
        elif roll == 1:
            events.append(MessageEvent("You feel like you are being watched."))
        elif roll == 2:
            events.append(MessageEvent("A shiver runs down your spine."))
        # C's default: no message (unfortunately no eerie_time to
        # guarantee one on the first visit)
        if not rng.rn2(5):
            # C: makemon(PM_GHOST, u.ux, u.uy, MM_NOMSG) -- pyhack's
            # makemon reads a position on the hero's square as
            # "near the hero" (enexto), which is C's "appears next to
            # you"
            ghost = makemon(world, rng, MONS[PM_GHOST], world.hero.pos, MmFlags.NOMSG)
            if ghost is not None:
                ngen = world.mon_state.mvitals[PM_GHOST].born
                if can_see(world, ghost.pos):
                    events.append(
                        MessageEvent(
                            f"A{'n enormous' if ngen < 5 else ''} ghost "
                            f"appears next to you{'!' if ngen < 10 else '.'}"
                        )
                    )
                else:
                    events.append(MessageEvent("You sense a presence close by!"))
                ghost.mpeaceful = False
                set_malign(world, ghost)
                # C: nomul(-3) -- "frightened to death, and unable to
                # move"; pyhack has no stun occupation yet
    return events


# ============================================================
# The refused entry points (C: src/pray.c)
# ============================================================


def do_pray(world: World) -> List[Event]:
    """C: dopray() (src/pray.c) -- the REFUSAL.  The prayer system
    (sacrifice, donation, altar wrath, the priest_talk service
    economy) is not ported (PLAN-SPECIAL-ROOMS.md §2.6 / §5.1), so the
    command answers with C's own line for praying at a shrine the hero
    is not aligned with -- the right answer for every altar until
    pray.c lands."""
    del world
    return [MessageEvent("You feel you should not do that here.")]


def do_offer(world: World) -> List[Event]:
    """C: doffer() (src/pray.c) -- the REFUSAL (see do_pray)."""
    del world
    return [MessageEvent("You feel you should not do that here.")]


__all__ = [
    "N_DIRS",
    "do_offer",
    "do_pray",
    "findpriest",
    "has_shrine",
    "induced_align",
    "intemple",
    "priestini",
]
