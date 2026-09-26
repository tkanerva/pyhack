"""The hero hits a monster (port of src/uhitm.c).

The mirror of ``core.mhitu`` (monster hits hero): the pipeline that runs
when the *hero* attacks a monster.  Written to the same pyhack event
model -- the functions here are **producers**: they decide what happened
and emit ``DamageEvent`` / ``MessageEvent`` *intents* without mutating
hit points.  ``rules.process_events`` (the pure functional core) applies
those intents through the state-mutation choke points (``apply_damage``
is the only place an actor loses HP).

Design notes (per the porting guidelines + architecture):

- The target is a runtime ``Monster`` that carries a ``PerMonst``
  (``mon.mdata``) -- its AC and special-attack data come from the
  ``core.monst`` / ``core.mondata`` port.  The hero is ``world.hero``
  (a ``Monster`` with ``is_hero=True``) and attacks with its flat stats
  (``damage`` = 1d``damage`` bare hands); the hero has no wielded weapon
  in the runtime yet, so the weapon / skill / magic-hit bonuses are not
  applied (they come with the hero weapon port -- ``core.weapon`` already
  provides ``hitval`` / ``dmgval`` for that).
- ``step`` routes a hero->monster hit here only when the *defender* has
  ``mdata is not None``; flat-stat demo monsters keep the simple
  ``rules.melee_attack`` path.  Symmetric with the mhitu hook.
- RNG: C's ``rnd(n)`` / ``d(n, x)`` are rolled via the runtime
  ``rng.randint`` duck-type (``_rnd`` / ``_dice``), keeping the module
  deterministic under the existing seeds.

Included (implemented and tested):

- ``uhitm`` -- the main entry: roll the to-hit (``known_hitum``) and, on
  a hit, deal the hero's bare-hand damage as a ``DamageEvent``; on a
  miss, a "You miss." message;
- ``known_hitum`` -- the to-hit target number (``20 - monster AC`` in the
  current runtime; the weapon / skill bonus is deferred);
- ``backstabbable`` -- the pure "can this monster be backstabbed?"
  predicate (no backstab bonus is applied yet, since the hero has no
  one-handed weapon);
- ``hmonas`` -- "is the hero, as a monster, the same type as the target?"
  (always False until the hero can be polymorphed).

STUBs (raise ``NotImplementedError``; the fill-in replaces a stub, not a
call site -- the C API surface stays visible):

- ``hitum`` / ``hmon_hitmon`` and the ``hmon_hitmon_*`` family -- the
  full hit handler (weapon damage, poison, silver, jousting, stagger,
  cleave, ...); needs the hero weapon / equipment machinery;
- ``hitum_cleave`` -- cleaving to adjacent monsters; needs a weapon;
- ``double_punch`` -- two-weapon combat; needs the hero weapon slots;
- ``mhitm_really_poison`` / ``theft_petrifies`` -- poisoned /
  theft-petrify weapons; need the hero weapon;
- ``steal_it`` -- a leprechaun steals your gold; needs the money system;
- ``mhitm_mgc_atk_negated`` -- magical-attack negation by the target's
  armor; needs the equipment / ``magic_negation`` machinery;
- ``gulpum`` -- the monster swallows the hero (the hero-side of the
  swallow); needs the swallow machinery (paired with ``mhitu.gulpmu``);
- ``joust`` / ``start_engulf`` / ``end_engulf`` -- riding / engulfment;
  need the steed machinery;
- ``demonpet`` -- a demon pet is summoned; needs the pet machinery;
- ``nohandglow`` / ``mhurtle_to_doom`` / ``first_weapon_hit`` /
  ``shade_aware`` -- the per-instance monster / artifact hooks;
- ``dynamic_multi_reason`` -- the multi-strike reason string; needs the
  xN-attack system.

Simplifications (documented, not bugs):

- The hero attacks once with bare hands; no multi-strike, cleave,
  double-punch, or weapon effects (all deferred, above).
- The monster's defensive reactions (``mdefend``: resist, counter-attack,
  slip free) are not modelled here -- a hit simply deals damage.  Those
  come with the per-instance monster model (the mon.c port).
- Because damage is applied by the core *after* the turn's events are
  produced, the hero cannot react to the target dying mid-sequence the
  way C does; a single hero attack has no such sequence, so this is
  unobservable.
"""
from __future__ import annotations

from typing import List, Optional

from .events import DamageEvent, Event, MessageEvent
from .mondata import is_flyer
from .monst import (Attack, MZ_LARGE, PerMonst, S_BLOB, S_ELEMENTAL, S_EYE,
                    S_FUNGUS, S_JELLY, S_LIGHT, S_VORTEX)
from .types import DamageType, Monster, World

# ------------------------------------------------------------
# RNG adapters (C rnd/d over the runtime rng.randint duck-type)
# ------------------------------------------------------------

def _rnd(rng, n: int) -> int:
    """C ``rnd(n)``: a roll in 1..n."""
    return rng.randint(1, n)


def _dice(rng, n: int, x: int) -> int:
    """C ``d(n, x)``: the sum of ``n`` dice of ``x`` sides (1..x each)."""
    if n <= 0 or x <= 0:
        return 0
    return sum(rng.randint(1, x) for _ in range(n))


# ------------------------------------------------------------
# To-hit (C: known_hitum)
# ------------------------------------------------------------

def known_hitum(mon: Monster, hero: Monster) -> int:
    """The target number the hero must roll (d20) at or under to hit
    ``mon`` (C: known_hitum).

    In the current runtime the hero has no weapon or skill, so the bonus
    is 0 and the target number is simply ``20 - monster AC`` (the same
    convention the simple ``rules.melee_attack`` path uses).  The full
    weapon / skill / magic-hit bonus comes with the hero weapon port
    (``core.weapon`` already provides ``hitval`` / ``dmgval``).
    """
    return 20 - mon.mdata.ac


# ------------------------------------------------------------
# Pure predicates
# ------------------------------------------------------------

def backstabbable(mon: Monster) -> bool:
    """True if the monster can be backstabbed (C: backstabbable): it does
    not fly, is not large or bigger, and has a normal body (not an
    amorphous / eye / light / vortex form).

    The backstab *bonus* is not applied yet because the hero has no
    one-handed weapon; this predicate is provided for the hero weapon
    port.
    """
    mdat: Optional[PerMonst] = mon.mdata
    if mdat is None:
        return False
    if is_flyer(mdat):
        return False
    if mdat.msize >= MZ_LARGE:
        return False
    if mdat.mlet in (S_BLOB, S_EYE, S_LIGHT, S_VORTEX, S_JELLY, S_FUNGUS,
                     S_ELEMENTAL):
        return False
    return True


def hmonas(mon: Monster, hero: Monster) -> bool:
    """True if the hero, as a monster, is the same type as ``mon``
    (C: hmonas).  In the current runtime the hero has no ``PerMonst``
    type (no polymorph), so this is always False; it becomes live once
    the hero can be polymorphed.
    """
    return (hero.mdata is not None and mon.mdata is not None
            and hero.mdata.pmidx == mon.mdata.pmidx)


# ------------------------------------------------------------
# The main entry point (C: uhitm)
# ------------------------------------------------------------

def uhitm(world: World, mon_id: str, rng) -> List[Event]:
    """The hero attacks the monster at ``mon_id`` (C: uhitm).

    Rolls the to-hit (``known_hitum``) and, on a hit, deals the hero's
    bare-hand damage as a ``DamageEvent``; on a miss, a "You miss."
    message.  Returns the list of event *intents* -- it does NOT mutate
    any state; ``rules.process_events`` applies them.  Targets without a
    ``PerMonst`` type (``mon.mdata is None``) are not handled here; they
    use the simple melee path in ``step``.
    """
    mon = world.actors[mon_id]
    hero = world.hero
    if mon.mdata is None or not mon.alive or not hero.alive:
        return []

    threshold = known_hitum(mon, hero)
    roll = _rnd(rng, 20)
    if roll <= threshold:
        dmg = _dice(rng, 1, hero.damage)
        events: List[Event] = [
            MessageEvent(f"⚔️ You hit {mon.name} for {dmg} damage.")
        ]
        if dmg > 0:
            events.append(DamageEvent(target=mon_id, amount=dmg,
                                      damage_type=DamageType.MELEE,
                                      source="player"))
        return events
    return [MessageEvent("🛡️ You miss.")]


# ------------------------------------------------------------
# STUBs -- the C API surface, filled by the named ports
# ------------------------------------------------------------

def hitum(mon: Monster, mattk: Attack) -> bool:
    """STUB (C: hitum): the hero's full hit handler for one of the
    monster's attack forms.  Needs the hero weapon / equipment machinery
    -- the hero weapon port."""
    raise NotImplementedError("hitum: the hero weapon path is not ported yet")


def hmon_hitmon(mon: Monster, obj, hitbonus: int, dambonus: int) -> bool:
    """STUB (C: hmon_hitmon): the hero hits a monster with ``obj`` (a
    weapon or thrown object).  The whole ``hmon_hitmon_*`` family
    (barehands / weapon_melee / weapon_ranged / potion / misc_obj /
    poison / jousting / stagger / cleave / silver / light) hangs off this
    and needs the hero weapon / equipment machinery -- the hero weapon
    port."""
    raise NotImplementedError("hmon_hitmon: the hero weapon path is not ported yet")


def hitum_cleave(mon: Monster, mattk: Attack) -> bool:
    """STUB (C: hitum_cleave): cleaving the kill to adjacent monsters.
    Needs the hero weapon (two-handed cleave) and the adjacency scan --
    the hero weapon / mon.c ports."""
    raise NotImplementedError("hitum_cleave: cleaving is not ported yet")


def double_punch() -> bool:
    """STUB (C: double_punch): the hero's two-weapon second attack.
    Needs the hero weapon slots -- the hero weapon port."""
    raise NotImplementedError("double_punch: two-weapon combat is not ported yet")


def mhitm_really_poison(mon: Monster, mattk: Attack, hero: Monster,
                        mhm) -> None:
    """STUB (C: mhitm_really_poison): apply a poisoned-weapon attack to
    the hero.  Needs the hero weapon (opoisoned) -- the hero weapon port."""
    raise NotImplementedError("mhitm_really_poison: weapon poison is not ported yet")


def theft_petrifies(obj) -> bool:
    """STUB (C: theft_petrifies): whether a theft-petrifying weapon is in
    play.  Needs the hero weapon -- the hero weapon port."""
    raise NotImplementedError("theft_petrifies: the hero weapon is not ported yet")


def steal_it(mon: Monster, mattk: Attack) -> None:
    """STUB (C: steal_it): a greedy monster (leprechaun) steals the
    hero's gold.  Needs the money system -- the money port."""
    raise NotImplementedError("steal_it: the money system is not ported yet")


def mhitm_mgc_atk_negated(magr: Monster, mdef: Monster,
                          verbosely: bool) -> bool:
    """STUB (C: mhitm_mgc_atk_negated): whether the target's armor /
    protection negates a magical attack.  Needs the equipment /
    ``magic_negation`` machinery -- the do_wear / artifact ports."""
    raise NotImplementedError("mhitm_mgc_atk_negated: equipment is not ported yet")


def gulpum(mon: Monster, mattk: Attack) -> int:
    """STUB (C: gulpum): the monster swallows the hero (the hero-side of
    the swallow, paired with ``mhitu.gulpmu``).  Needs the swallow
    machinery -- the mon.c / swallow port."""
    raise NotImplementedError("gulpum: swallowing is not ported yet")


def joust(mon: Monster, obj) -> int:
    """STUB (C: joust): the hero jousts while riding.  Needs the steed
    machinery -- the steed port."""
    raise NotImplementedError("joust: riding is not ported yet")


def start_engulf(mon: Monster) -> None:
    """STUB (C: start_engulf): begin engulfing the hero (on a steed).
    Needs the steed / swallow machinery."""
    raise NotImplementedError("start_engulf: the steed is not ported yet")


def end_engulf() -> None:
    """STUB (C: end_engulf): finish engulfing the hero.  Needs the steed /
    swallow machinery."""
    raise NotImplementedError("end_engulf: the steed is not ported yet")


def demonpet() -> None:
    """STUB (C: demonpet): a demon pet is summoned for the hero.  Needs
    the pet machinery -- the pet port."""
    raise NotImplementedError("demonpet: pets are not ported yet")


def nohandglow(mon: Monster) -> None:
    """STUB (C: nohandglow): clear the "no-hand" glow effect on a monster.
    Needs the per-instance monster model -- the mon.c port."""
    raise NotImplementedError("nohandglow: not ported yet")


def mhurtle_to_doom(mon: Monster, n, pdat) -> bool:
    """STUB (C: mhurtle_to_doom): the hurl-to-doom special.  Needs the
    per-instance monster model -- the mon.c port."""
    raise NotImplementedError("mhurtle_to_doom: not ported yet")


def first_weapon_hit(obj) -> None:
    """STUB (C: first_weapon_hit): bookkeeping for the hero's first hit
    with a weapon this turn.  Needs the hero weapon -- the hero weapon
    port."""
    raise NotImplementedError("first_weapon_hit: the hero weapon is not ported yet")


def shade_aware(obj) -> bool:
    """STUB (C: shade_aware): whether the hero is aware they are holding a
    shade's item.  Needs the hero inventory / corpse machinery."""
    raise NotImplementedError("shade_aware: not ported yet")


def dynamic_multi_reason(mon: Monster, verb: str, by_gaze: bool) -> str:
    """STUB (C: dynamic_multi_reason): build the multi-strike reason
    string.  Needs the xN-attack system -- the multi port."""
    raise NotImplementedError("dynamic_multi_reason: multi-strike is not ported yet")
