"""Where a monster (or an object) may stand: goodpos / enexto.

Port of the placement half of src/teleport.c.  These two functions are
the choke point every "put a monster on the map" caller goes through --
makemon() (a random square, a requested square, an adjacent square), the
level generator (a room square), and later mnexto() (level change),
teleportation and the shopkeeper's door guard.  Keeping them here
instead of inside core.makemon is the same reason core.rules holds
apply_damage: one place to grow.

C provenance:

  src/teleport.c  goodpos(), goodpos_onscary(), enexto(),
                  enexto_gpflags(), enexto_core() (the !NEW_ENEXTO body,
                  which is what the 5.0 default build compiles),
                  may_passwall(), is_waterwall()

The gpflags are C's "good position" flags, which share their bit space
with makemon()'s MM_ flags (hack.h); they are re-exported from here so a
caller can spell them without importing core.makemon.

Everything is a function of (world, rng, map_, lev, ...): the Map is a
parameter because a level may be generated while the hero still stands
on the previous one (PLAN-MKLEV.md decision 3), and `lev` says which
level's monsters the occupancy tests should see.  The rng is explicit
because C's goodpos() itself draws -- the eel's "is it in water?" roll
(`rn2(13)`) -- which is why the "which square" decisions cannot be
separated from the level's draw sequence.

STUBs (announced where they are, each with the machinery it waits for):

  - ``onscary()`` and the GP_CHECKSCARY test: the scroll of scare
    monster on the floor and engraved Elbereth are not ported, so
    nothing is ever "scary" and the flag is accepted and ignored.
  - ``is_exclusion_zone(LR_MONGEN, ...)``: level regions are a special
    level feature (PLAN-SPLEV.md), so nothing is ever excluded.
  - the boulder test: nothing places a boulder yet (the object type
    exists, the generation does not), so ``_boulder_at`` is False.
  - In ``goodpos``: the hero's own water / lava cases (swimming,
    levitation, wading) need the hero-state properties; the tests below
    are the monster ones plus "may a monster of this type be there at
    all", which is what the generators ask.
  - ``m_in_air()`` drops the C ceiling test (pyhack has no ceiling):
    a flyer, a floater or a clinger is in the air.
  - The long-worm-segment case of goodpos (a worm may be placed back in
    its own square) is unported: a worm is a single monster here
    (PLAN-MAKEMON.md divergence 3).

Simplifications (documented, not bugs):

  - the water tests read the terrain only: pyhack has no water level
    and no waterwall, so ``Is_waterlevel`` is the constant False and the
    `m_in_air` half is what lets a flyer cross a pool.
"""

from __future__ import annotations

from typing import List, Optional

from .mondata import (amorphous, is_clinger, is_floater, is_flyer,
                      is_swimmer, likes_lava, passes_walls, throws_rocks)
from .monst import PM_FLOATING_EYE, PerMonst, S_EEL
from .types import (GP_ALLOW_U, GP_ALLOW_XY, GP_AVOID_MONPOS, GP_CHECKSCARY,
                    MM_IGNORELAVA, MM_IGNOREWATER, Map, Pos, World,
                    accessible, is_door, is_lava, is_pool, is_wall)

# C: teleport.c MAX_GOOD -- how many candidates enexto_core() collects on
# the ring it settles on before it stops looking.
MAX_GOOD = 15


# ------------------------------------------------------------
# Small predicates (C: teleport.c / hack.h macros)
# ------------------------------------------------------------

def m_in_air(mdat: PerMonst) -> bool:
    """C: m_in_air -- the monster is off the ground.  STUB: the C
    `is_clinger(mdat) && has_ceiling(...)` half drops the ceiling test,
    pyhack levels have no ceiling."""
    return is_flyer(mdat) or is_floater(mdat) or is_clinger(mdat)


def is_waterwall(pos: Pos) -> bool:
    """C: is_waterwall -- the Plane of Water's walls.  No such terrain
    here, so always False (kept as the named predicate the C tests
    short-circuit on)."""
    del pos
    return False


def may_passwall(map_: Map, pos: Pos) -> bool:
    """C: may_passwall -- may a wall-walker pass into this square?  In C
    that means a wall (or undiggable stone which it cannot); here: stone
    or any wall type."""
    return is_wall(map_.tile_at(pos).typ)


def closed_door(map_: Map, pos: Pos) -> bool:
    """C: closed_door -- a DOOR that is closed or locked."""
    tile = map_.tile_at(pos)
    return is_door(tile.typ) and not tile.is_door_open()


def onscary(world: World, map_: Map, lev: int, pos: Pos,
            mdat: PerMonst) -> bool:
    """C: onscary -- is `pos` a square this monster is afraid of?

    STUB: the two sources are a scroll of scare monster lying on the
    square and an Elbereth engraving; neither is ported (no floor-item
    scare, no engravings), so nothing scares anything yet.  The argument
    list is the C one so the fill-in is a body swap.
    """
    del world, map_, lev, pos, mdat
    return False


def _boulder_at(world: World, lev: int, pos: Pos) -> bool:
    """C: sobj_at(BOULDER, x, y) -- a boulder on the square.

    STUB: the object type exists (core.objects) but nothing generates a
    boulder yet, so the answer is always "no boulder".  The C call is
    named here for the fill-in.
    """
    del world, lev, pos
    return False


# ------------------------------------------------------------
# goodpos (C: src/teleport.c goodpos)
# ------------------------------------------------------------

def goodpos(world: World, rng, map_: Map, lev: int, pos: Pos,
            mdat: Optional[PerMonst] = None,
            gpflags: int = 0) -> bool:
    """Is `pos` a good position for a monster of type `mdat` (or, with
    mdat None, for an object)?  C: teleport.c#goodpos.

    The subset, in the C order: in bounds; not the hero's square (unless
    GP_ALLOW_U); not already occupied (GP_AVOID_MONPOS); the per-type
    terrain tests (water, lava, wall-walking, amorphous through a closed
    door, the eel's water preference) -- which RETURN, as C's do, so a
    swimmer or a flyer over a pool is good and never reaches the
    ACCESSIBLE test below; accessible terrain, closed doors included (C:
    monmove.c#accessible); no boulder; no exclusion zone.  The hero's own
    water/lava cases and the long-worm-segment case are not ported -- see
    the module docstring.
    """
    allow_u = (gpflags & GP_ALLOW_U) != 0
    avoid_monpos = (gpflags & GP_AVOID_MONPOS) != 0
    ignorewater = (gpflags & MM_IGNOREWATER) != 0
    ignorelava = (gpflags & MM_IGNORELAVA) != 0
    checkscary = (gpflags & GP_CHECKSCARY) != 0

    if not map_.in_bounds(pos):
        return False

    if not allow_u:
        hero = world.hero_or_none
        if hero is not None and hero.lev == lev and hero.pos == pos:
            return False

    if avoid_monpos and world.monster_at_lev(lev, pos) is not None:
        return False

    typ = map_.tile_at(pos).typ

    if mdat is not None:
        if is_pool(typ) and not ignorewater:
            # C returns here rather than falling through, so a swimmer
            # or a monster in the air is good on water even though
            # water is not ACCESSIBLE.  C's hero case is not modelled;
            # water levels are unported, so the Is_waterlevel /
            # is_waterwall tests are constantly false.
            return is_swimmer(mdat) or (not is_waterwall(pos)
                                        and m_in_air(mdat))
        elif mdat.mlet == S_EEL and rng.rn2(13) and not ignorewater:
            # an eel out of water is refused 12 times in 13 (C draws
            # this, which is why goodpos() takes the level's rng)
            return False
        elif is_lava(typ) and not ignorelava:
            # C: the floating eye dries out over lava even though it
            # could float above it (kept: a property of the species)
            if mdat.pmidx == PM_FLOATING_EYE:
                return False
            return m_in_air(mdat) or likes_lava(mdat)
        if passes_walls(mdat) and may_passwall(map_, pos):
            return True
        if amorphous(mdat) and closed_door(map_, pos):
            return True
        if checkscary and onscary(world, map_, lev, pos, mdat):
            return False

    # C: accessible() -- ACCESSIBLE() *and* not a closed door, which is
    # what stops a land monster being put behind one (monmove.c)
    if not accessible(typ) or closed_door(map_, pos):
        if not (is_pool(typ) and ignorewater) \
                and not (is_lava(typ) and ignorelava):
            return False

    if _boulder_at(world, lev, pos) \
            and (mdat is None or not throws_rocks(mdat)):
        return False

    # C: `is_exclusion_zone(LR_MONGEN, x, y)` when avoid_monpos -- a
    # special-level region feature (PLAN-SPLEV.md), never excluded here.
    return True


# ------------------------------------------------------------
# enexto (C: src/teleport.c enexto / enexto_gpflags / enexto_core)
# ------------------------------------------------------------

def enexto(world: World, rng, map_: Map, lev: int, origin: Pos,
           mdat: Optional[PerMonst] = None) -> Optional[Pos]:
    """The nearest good square to `origin` for a monster of type `mdat`,
    or None.  C: enexto -- GP_CHECKSCARY first, then without it.

    Returns the position instead of C's coord-out-parameter + boolean
    (the pyhack style: "no square" is None, not an exception).
    """
    got = enexto_core(world, rng, map_, lev, origin, mdat, GP_CHECKSCARY)
    if got is not None:
        return got
    return enexto_core(world, rng, map_, lev, origin, mdat, 0)


def enexto_gpflags(world: World, rng, map_: Map, lev: int, origin: Pos,
                   mdat: Optional[PerMonst] = None,
                   entflags: int = 0) -> Optional[Pos]:
    """C: enexto_gpflags -- like enexto with caller flags, both passes
    keeping them (the scary check is added to the first)."""
    got = enexto_core(world, rng, map_, lev, origin, mdat,
                      GP_CHECKSCARY | entflags)
    if got is not None:
        return got
    return enexto_core(world, rng, map_, lev, origin, mdat, entflags)


def enexto_core(world: World, rng, map_: Map, lev: int, origin: Pos,
                mdat: Optional[PerMonst] = None,
                entflags: int = 0) -> Optional[Pos]:
    """C: enexto_core -- walk the square rings around `origin` outwards
    and take a random one of the good squares on the first ring that has
    any (at most MAX_GOOD of them, which is also where C stops).

    The ring walk is C's exactly: the top and bottom rows of the ring
    left to right, then the left and right columns between them, so the
    candidate order -- and therefore what `rn2(len(good))` picks -- is
    the sequence the C code would visit.
    """
    allow_xx_yy = (entflags & GP_ALLOW_XY) != 0
    entflags &= ~GP_ALLOW_XY
    xx, yy = origin

    # C: max(xx - 1, (COLNO - 1) - xx), max(yy - 0, (ROWNO - 1) - yy)
    # -- the map's edge ring is wall, and column 0 is never a position
    xdist = max(xx - 1, (map_.width - 1) - xx)
    ydist = max(yy, (map_.height - 1) - yy)
    rangemax = max(xdist, ydist)

    good: List[Pos] = []
    range_ = 1
    while True:
        xmin = max(1, xx - range_)
        xmax = min(map_.width - 1, xx + range_)
        ymin = max(0, yy - range_)
        ymax = min(map_.height - 1, yy + range_)

        for x in range(xmin, xmax + 1):
            if goodpos(world, rng, map_, lev, (x, ymin), mdat, entflags):
                good.append((x, ymin))
                if len(good) >= MAX_GOOD:
                    break
            if goodpos(world, rng, map_, lev, (x, ymax), mdat, entflags):
                good.append((x, ymax))
                if len(good) >= MAX_GOOD:
                    break
        if len(good) < MAX_GOOD:
            for y in range(ymin, ymax):
                if goodpos(world, rng, map_, lev, (xmin, y), mdat, entflags):
                    good.append((xmin, y))
                    if len(good) >= MAX_GOOD:
                        break
                if goodpos(world, rng, map_, lev, (xmax, y), mdat, entflags):
                    good.append((xmax, y))
                    if len(good) >= MAX_GOOD:
                        break
        range_ += 1
        if good or range_ > rangemax:
            break

    if not good:
        # C: the caller may allow <xx,yy> itself as the last resort
        if allow_xx_yy and goodpos(world, rng, map_, lev, origin, mdat,
                                   entflags):
            return origin
        return None
    # C: i = rn2(good_ptr - good) -- one of the candidates, at random
    return good[rng.rn2(len(good))]


__all__ = [
    "GP_ALLOW_XY", "GP_ALLOW_U", "GP_CHECKSCARY", "GP_AVOID_MONPOS",
    "MAX_GOOD",
    "closed_door", "enexto", "enexto_core", "enexto_gpflags", "goodpos",
    "is_waterwall", "m_in_air", "may_passwall", "onscary",
]
