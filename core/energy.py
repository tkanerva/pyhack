"""Spell power (Pw): the uen / uenmax / uenpeak bookkeeping + regen.

C provenance: src/u_init.c (`u.uen = u.uenmax = u.uenpeak = newpw()`),
src/spell.c (`newpw()` -- the starting-Pw table, `regen_pw()` -- the
per-turn recharge, the `spelleffects()` drain) and include/you.h
(`SPELL_LEV_PW(x)` -- a level-`x` spell costs 5*x Pw; the uen /
uenmax / uenpeak / ueninc[] fields).

The demo's fixed-Wizard hero (core.worldgen, C role.c: INT 15, WIS 12)
starts with the C low-level branch of newpw() -- `4 + 1 + rnd(3)`, ONE
rng draw, 6..8 Pw -- and regenerates 1 Pw every (MAXULEV + 8 -
ulevel) turns (the C regen period), up to uenmax.  Casting
(core.spells.cast_spell) checks the cost against uen BEFORE the
failure roll and drains it after a successful cast (C check order);
this module owns the arithmetic only.

``ueninc[]`` is the per-level Pw INCREMENT (C you.h: "increases to
uenmax for each level gain"), not the regen period: C's newpw()
records it ("remember increment; future level drain could take it
away again"), losexp() subtracts it.  init_energy records the
starting Pw in the init slot (ueninc[0], as C's u_init runs at level
0); experience.pluslvl records each level-up's gain at the OLD level;
experience.losexp reads the new level's slot.  The regen period is
computed from the level directly, as in C's regen_pw
(`(MAXULEV + 8 - u.ulevel) * (wizard ? 3 : 4) / 6`; the demo uses the
base period).
"""
from __future__ import annotations

from typing import List

from .events import Event
from .types import MAXULEV, World


def spell_lev_pw(lev: int) -> int:
    """C: SPELL_LEV_PW(x) (include/you.h) -- the Pw cost of a
    level-`lev` spell: 5 * level."""
    return 5 * lev


def newpw(ulevel: int, rng) -> int:
    """C: newpw() (src/spell.c) -- the Pw a fresh character of
    `ulevel` starts with.

    The low-level branch is C's exactly: `4 + 1 + rnd(3)` (ONE draw,
    6..8 Pw).  The higher levels follow the C table (1: 4, 5: 10,
    10: 21, 20: 40, 30: 60) by linear interpolation without the
    per-level jitter (documented simplification -- the demo hero is
    level 1 and never leaves the first branch).
    """
    if ulevel < 2:
        return 4 + 1 + rng.randint(1, 3)
    if ulevel < 5:
        return 4 + (ulevel - 1) * 2
    if ulevel < 10:
        return 10 + (ulevel - 5)
    if ulevel < 20:
        return 21 + (ulevel - 10) * 2
    if ulevel < 30:
        return 40 + (ulevel - 20) * 2
    return 60


def init_energy(world: World, rng) -> None:
    """C: u_init.c -- `u.uen = u.uenmax = u.uenpeak = newpw();`, with
    the newpw increment record: C's newpw() writes `u.ueninc[u.ulevel]
    = en` (the u_init call runs at level 0, so the init slot is
    ueninc[0], as with uhpinc[0]).

    Adds exactly ONE rng draw (the newpw rnd(3)).
    """
    hero = world.hero
    pw = newpw(hero.ulevel, rng)
    hero.uen = hero.uenmax = hero.uenpeak = pw
    hero.ueninc[0] = pw


def drain_energy(world: World, actor_id: str, amount: int) -> None:
    """C: the drain in spelleffects() -- after a successful cast, the
    cost is subtracted from the caster's Pw (floored at 0)."""
    actor = world.actors[actor_id]
    actor.uen = max(0, actor.uen - amount)


def tick_energy(world: World, turn: int, rng) -> List[Event]:
    """C: regen_pw() -- the hero regains 1 Pw every (MAXULEV + 8 -
    ulevel) turns, up to uenmax.  Silent (C emits no message on
    regen) and draw-free; `turn` is the number of the turn being
    played (step passes world.turn + 1).

    The period is computed from the level, as in C's regen_pw -- NOT
    read from ueninc[], which is the per-level Pw increment (the C
    newpw / losexp bookkeeping; see the module docstring).
    """
    hero = world.hero
    if not hero.alive or hero.uen >= hero.uenmax:
        return []
    if 1 <= hero.ulevel <= MAXULEV:
        period = MAXULEV + 8 - hero.ulevel
    else:
        period = MAXULEV + 7
    if period > 0 and turn % period == 0:
        hero.uen += 1
    return []
