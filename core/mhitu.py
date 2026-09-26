"""Monster hits the hero (port of src/mhitu.c).

This is the "mhitu" half of monster combat: the pipeline that runs when
a monster attacks the hero.  It is written to the pyhack event model:
the functions here are **producers** -- they decide what happened and
emit `DamageEvent` / `StatusEvent` / `MessageEvent` *intents*, they do
NOT mutate hit points or statuses.  The pure functional core
(``rules.process_events``) consumes those intents and routes them through
the state-mutation choke points (``apply_damage`` is the only place an
actor loses HP; the status setters are the only place a status changes).

Design notes (per the porting guidelines + architecture):

- The attacker is a runtime ``Monster`` that carries a ``PerMonst``
  (``mon.mdata``) -- the attack tables, level and flags come from the
  ``core.monst`` / ``core.mondata`` port.  Monsters without ``mdata``
  (the flat-stat demo monsters) do NOT use this module; they keep the
  simple ``rules.melee_attack`` path.  ``step`` routes a monster->hero
  hit here only when ``mon.mdata is not None``.
- The hero is ``world.hero`` (a ``Monster`` with ``is_hero=True``).
- Status questions go through the ``core.hacklib`` query functions
  (``is_blind`` / ``is_confused`` / ``can_see`` / ``is_stuck``) -- no raw
  flag reads.
- RNG: the runtime rng duck-type exposes ``.randint(a, b)`` / ``.choice``
  (the core ``Rng`` and the demo ``SeqRng`` / ``random.Random`` all do),
  so C's ``rnd(n)`` / ``d(n, x)`` are rolled via ``_rnd`` / ``_dice``
  below.  This keeps the module deterministic under the existing seeds.

Included (implemented and tested):

- ``adtyp_to_damage`` -- map a C damage type (AD_*) to the game
  ``DamageType``;
- ``getmattk`` -- pick the monster's next attack, applying the
  pure-data substitutions that need no unported state (the
  "two consecutive disease attacks" rule);
- ``mattacku`` -- the main loop: for each of the monster's attacks,
  roll the hit differential (C: ``tmp = AC + 10 + m_lev``, -2 if
  trapped) and dispatch to ``hitmu`` / ``missmu`` / ``explmu``;
- ``hitmu`` -- a successful hit: base damage ``d(damn, damd)`` (+ the
  undead-at-midnight extra), the negative-AC damage reduction, the
  damage type, and any disease/confusion/sleep status the attack
  carries -- emitted as a ``DamageEvent`` + ``StatusEvent``s;
- ``missmu`` -- the "misses!" / "just misses!" message;
- ``explmu`` -- an exploder (e.g. yellow light) detonates: the hero is
  blinded / hallucinates / takes elemental damage, and the attacker
  takes the full explosion as self-damage (so it dies);
- ``hitmsg`` -- the "<monster> bites / kicks / hits you" verb message;
- ``could_seduce`` -- the pure seduction-eligibility predicate (0/1/2);
- ``mtrapped_in_pit`` -- scoped trap test (a stuck monster is treated as
  trapped);
- ``passiveum`` -- the hero's passive counterattack; a no-op while the
  hero has no ``mdata`` (it becomes live once the hero can be
  polymorphed into a monster with passive attacks).

STUBs (raise ``NotImplementedError``; the fill-in replaces a stub, not a
call site -- the C API surface stays visible):

- ``gulpmu`` / ``expels`` / ``gulp_blnd_check`` -- swallowing
  (needs the ``u.uswallow`` / ``u.ustuck`` / ``u.uswldtim`` machinery);
- ``gazemu`` -- gazes (needs LOS, stone resistance, polymorph);
- ``doseduce`` / ``mayberem`` -- seduction (needs equipment, money,
  alignment);
- ``summonmu`` -- demon / were-creature summoning (needs ``msummon`` /
  ``were_summon``, night, Inhell);
- ``u_slip_free`` / ``magic_negation`` -- armor-based protection
  (needs the equipment / artifact machinery);
- ``mon_avoiding_this_attack`` / ``ranged_attk_available`` -- ranged
  attack availability (needs the ``m_seenres`` bookkeeping);
- ``cloneu`` -- the gelatinous-cube split (needs the monster-spawn
  machinery);
- ``u_slow_down`` -- intrinsic-speed loss (needs the ability/speed
  system).

Simplifications (documented, not bugs):

- No line-of-sight, hero invisibility, displacement or underwater state
  in the runtime yet, so ``wildmiss`` (attacking the wrong square) and
  the related AC adjustments are not modelled; the monster is assumed
  to see the hero when it is adjacent.  These come with the mon.c /
  vision ports.
- C's ``gm.multi`` (multi-strike) bonus is not modelled (no xN attacks).
- The "weird" contact damage types (drain life, petrify, slow, steal,
  drain-ability, ...) map to plain ``MELEE`` damage here: the damage
  rolls still apply, but the actual drain / petrify / slow / steal
  effects come with their respective ports.
- Because damage is applied by the core *after* the turn's events are
  produced, ``mattacku`` cannot react to an attacker dying mid-turn the
  way C does.  The core subset has no multi-attack monster that kills
  itself in one turn (self-detonators have a single attack), so this
  is unobservable today; it is noted here for the completion pass.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .events import DamageEvent, Event, MessageEvent, StatusEvent
from .hacklib import can_see, is_hallucinating, is_stuck
from .mondata import is_animal, is_undead
from .monst import (
    AD_ACID, AD_BLND, AD_COLD, AD_CONF, AD_DISE, AD_DISN, AD_ELEC, AD_FIRE,
    AD_FAMN, AD_HALU, AD_MAGM, AD_PHYS, AD_PEST, AD_SITM, AD_SLEE, AD_SEDU,
    AD_SSEX, AD_STUN, AD_DRST,
    AT_BITE, AT_BOOM, AT_BUTT, AT_ENGL, AT_EXPL, AT_HUGS, AT_KICK, AT_NONE,
    AT_STNG, AT_TENT, AT_TUCH, NATTK, Attack, PerMonst, PM_WOOD_NYMPH,
    distance_atk_type,
)
from .types import DamageType, Monster, World

# ------------------------------------------------------------
# Attack outcome codes (C: M_ATTK_* in hack.h / mhitm.h)
# ------------------------------------------------------------

M_ATTK_MISS = 0
M_ATTK_HIT = 1
M_ATTK_AGR_DIED = 2
M_ATTK_DEF_DIED = 4
M_ATTK_AGR_DONE = 8


# ------------------------------------------------------------
# C damage type (AD_*) -> game DamageType
# ------------------------------------------------------------

_AD_TO_DAMAGE = {
    AD_PHYS: DamageType.MELEE,
    AD_MAGM: DamageType.MAGIC_MISSILE,
    AD_FIRE: DamageType.FIRE,
    AD_COLD: DamageType.COLD,
    AD_SLEE: DamageType.SLEEP,
    AD_STUN: DamageType.SLEEP,
    AD_ELEC: DamageType.LIGHTNING,
    AD_ACID: DamageType.ACID,
    AD_DISN: DamageType.CANCELLATION,
    AD_DRST: DamageType.POISON,
    AD_DISE: DamageType.POISON,
}


def adtyp_to_damage(adtyp: int) -> DamageType:
    """Map a C damage type (AD_*) to the game's ``DamageType``.

    The game model has a coarser damage vocabulary than the C ``AD_*``
    set; the table above is the faithful fit.  The "weird" contact
    effects (drain, petrify, slow, steal, ...) fall back to ``MELEE`` --
    their damage rolls still apply, but the full mechanics come with
    their respective ports (see the module docstring).
    """
    return _AD_TO_DAMAGE.get(adtyp, DamageType.MELEE)


# ------------------------------------------------------------
# RNG adapters (C rnd/d over the runtime rng.randint duck-type)
# ------------------------------------------------------------

def _rnd(rng, n: int) -> int:
    """C ``rnd(n)``: a roll in 1..n."""
    return rng.randint(1, n)


def _dice(rng, n: int, x: int) -> int:
    """C ``d(n, x)``: the sum of ``n`` dice of ``x`` sides (1..x each).

    ``d(0, x)`` is 0 (and ``d(n, 0)`` is 0), matching C."""
    if n <= 0 or x <= 0:
        return 0
    return sum(rng.randint(1, x) for _ in range(n))


# ------------------------------------------------------------
# Attack selection (C: getmattk)
# ------------------------------------------------------------

def getmattk(mon: Monster, indx: int, prev_result: List[int]) -> Attack:
    """Select the monster's next attack (C: getmattk), possibly
    substituting for its usual one.

    Only the substitutions that need no unported state are implemented:
    a monster must not land two consecutive disease / hunger attacks on
    the same turn, so if the previous attack already hit and this one is
    the same disease / hunger type, it becomes a stun attack.  The other
    C branches (energy-scaled drain, holder/engulfer cooldown,
    barrow-wight weapon forcing, lich cold-touch, home-elemental double
    damage) need hero energy / per-instance monster state / artifacts /
    resistances and are deferred with those ports.
    """
    mdat: PerMonst = mon.mdata
    attk = mdat.mattk[indx]
    if (indx > 0
            and prev_result[indx - 1] > M_ATTK_MISS
            and attk.adtyp in (AD_DISE, AD_PEST, AD_FAMN)
            and attk.adtyp == mdat.mattk[indx - 1].adtyp):
        return Attack(attk.aatyp, AD_STUN, attk.damn, attk.damd)
    return attk


# ------------------------------------------------------------
# Message helpers
# ------------------------------------------------------------

def _hit_verb(mattk: Attack) -> str:
    """The verb for a hit message by attack type (C: hitmsg switch)."""
    aatyp = mattk.aatyp
    if aatyp == AT_BITE:
        return "bites"
    if aatyp == AT_KICK:
        return "kicks"
    if aatyp == AT_STNG:
        return "stings"
    if aatyp == AT_BUTT:
        return "butts"
    if aatyp == AT_TUCH:
        return "touches you"
    if aatyp == AT_TENT:
        return "tentacles suck your brain"
    if aatyp in (AT_EXPL, AT_BOOM):
        return "explodes"
    return "hits"


def hitmsg(mon: Monster, mattk: Attack) -> MessageEvent:
    """The "<monster> <verb>" line for a landed attack (C: hitmsg).

    C's hitmsg also has a seduction branch and an " again" suffix for
    repeated similar attacks; the seduction line is deferred with
    ``doseduce`` (STUB) and the " again" suffix is dropped (the console
    log already shows each hit).  The damage amount is not in the line
    (C shows it in the status line); it is carried by the accompanying
    ``DamageEvent``.
    """
    verb = _hit_verb(mattk)  # "touches you" already includes the object
    return MessageEvent(f"{mon.name} {verb}!")


def could_seduce(magr: Monster, mdef: Monster,
                 mattk: Optional[Attack]) -> int:
    """Returns 0 if seduction is impossible, 1 if fine, 2 if wrong
    gender for a nymph (C: could_seduce).

    Pure predicate over the two monsters' ``PerMonst`` types.  Only
    nymphs / the amorous demon seduce in the core subset; everything
    else returns 0.  The actual seduction *effect* (``doseduce``) is a
    STUB, so this is provided for the message logic and the future port.
    """
    if magr.mdata is None or mdef.mdata is None:
        return 0
    pagr = magr.mdata
    if is_animal(pagr):
        return 0
    adtyp = mattk.adtyp if mattk is not None else AD_SEDU
    if adtyp == AD_SSEX:
        adtyp = AD_SEDU
    # nymphs (S_NYMPH) and the amorous demon are the seducers; only the
    # wood nymph is in the core subset
    if pagr.pmidx != PM_WOOD_NYMPH:
        return 0
    if adtyp not in (AD_SEDU, AD_SITM):
        return 0
    return 1


# ------------------------------------------------------------
# Trap test (C: mtrapped_in_pit) -- scoped
# ------------------------------------------------------------

def mtrapped_in_pit(mon: Monster) -> bool:
    """True iff the monster is trapped in a (spiked) pit (C:
    mtrapped_in_pit).

    The runtime has no "monster standing in an active pit" state (traps
    trigger and are consumed), so a stuck monster (web / pit) is treated
    as trapped.  This is the -2-to-hit and the "can't kick" proxy.
    """
    return is_stuck(mon)


# ------------------------------------------------------------
# A hit (C: hitmu) -- produces events, returns (events, damage)
# ------------------------------------------------------------

def hitmu(world: World, mon: Monster, hero: Monster, mattk: Attack,
          rng, midnight: bool = False) -> Tuple[List[Event], int]:
    """The monster's attack landed on the hero (C: hitmu).

    Returns ``(events, damage)``: the ``DamageEvent`` / ``MessageEvent``
    / ``StatusEvent`` intents to emit, and the raw damage dealt (so the
    caller can stop producing further attacks once the hero is down).
    No state is mutated here -- ``process_events`` applies the events.
    """
    mdat: PerMonst = mon.mdata
    events: List[Event] = []

    # base damage d(damn, damd); undead at midnight deal it twice
    dmg = _dice(rng, mattk.damn, mattk.damd)
    if midnight and is_undead(mdat):
        dmg += _dice(rng, mattk.damn, mattk.damd)

    # negative armor class reduces damage instead of fully protecting
    if dmg and hero.ac < 0:
        dmg -= _rnd(rng, -hero.ac)
        if dmg < 1:
            dmg = 1

    events.append(hitmsg(mon, mattk))
    if dmg > 0:
        events.append(DamageEvent(target=hero.id, amount=dmg,
                                  damage_type=adtyp_to_damage(mattk.adtyp),
                                  source=mon.id))

    # status the attack carries (C: make_sick / make_confused / ...)
    if mattk.adtyp in (AD_DRST, AD_DISE):
        events.append(StatusEvent(hero.id, "poison", _rnd(rng, 20)))
    elif mattk.adtyp == AD_CONF:
        events.append(StatusEvent(hero.id, "confusion", _dice(rng, 3, 4)))
    elif mattk.adtyp == AD_SLEE:
        events.append(StatusEvent(hero.id, "sleep", _rnd(rng, 10)))

    # the hero's passive counterattack (a no-op until the hero can be a
    # monster with passive attacks, i.e. polymorph)
    events += passiveum(world, hero, mon, mattk, rng)

    return events, dmg


# ------------------------------------------------------------
# A miss (C: missmu)
# ------------------------------------------------------------

def missmu(mon: Monster, mattk: Attack, nearmiss: bool = False) -> List[Event]:
    """The monster missed the hero (C: missmu)."""
    word = "just " if nearmiss else ""
    return [MessageEvent(f"🛡️ {mon.name} {word}misses you!")]


# ------------------------------------------------------------
# Explosion (C: explmu)
# ------------------------------------------------------------

def explmu(world: World, mon: Monster, hero: Monster, mattk: Attack,
           rng) -> List[Event]:
    """The monster explodes in the hero's face (C: explmu).

    The hero is affected by the blast (blinded / hallucinating /
    elemental damage depending on the damage type) and the attacker takes
    the full blast as self-damage -- which is what kills an exploder.
    """
    mdat: PerMonst = mon.mdata
    # a cancelled exploder doesn't go off (C: if (mtmp->mcan) return)
    if getattr(mon, "mcan", 0):
        return []
    power = _dice(rng, mattk.damn, mattk.damd)
    events: List[Event] = [hitmsg(mon, mattk)]

    adtyp = mattk.adtyp
    if adtyp == AD_BLND and can_see(hero):
        events.append(StatusEvent(hero.id, "blind", power))
    elif adtyp == AD_HALU and not is_hallucinating(hero):
        events.append(StatusEvent(hero.id, "hallucination", power))
    elif adtyp in (AD_FIRE, AD_COLD, AD_ELEC):
        events.append(DamageEvent(target=hero.id, amount=power,
                                  damage_type=adtyp_to_damage(adtyp),
                                  source=mon.id))
    # the exploder dies: it takes the whole blast as self-damage
    events.append(DamageEvent(target=mon.id, amount=power,
                              damage_type=adtyp_to_damage(adtyp),
                              source=mon.id))
    return events


# ------------------------------------------------------------
# Passive counterattack (C: passiveum) -- scoped
# ------------------------------------------------------------

def passiveum(world: World, hero: Monster, mon: Monster, mattk: Attack,
              rng) -> List[Event]:
    """The hero's passive counterattack, if it is a monster with one
    (C: passiveum).

    In the current runtime the hero has no ``mdata`` (no polymorph), so
    there is no passive attack and this returns [].  The structure is in
    place for the acid / stone / disenchant passive cases that become
    live once the hero can be polymorphed into such a monster.
    """
    olduasmon = hero.mdata
    if olduasmon is None:
        return []
    oldu = None
    for a in olduasmon.mattk:
        if a.aatyp in (AT_NONE, AT_BOOM):
            oldu = a
            break
    if oldu is None:
        return []
    if oldu.damn:
        tmp = _dice(rng, oldu.damn, oldu.damd)
    elif oldu.damd:
        tmp = _dice(rng, olduasmon.mlevel + 1, oldu.damd)
    else:
        tmp = 0
    events: List[Event] = []
    if oldu.adtyp == AD_ACID and not is_undead(mon.mdata):
        if _rnd(rng, 2) == 1:
            events.append(MessageEvent(f"{mon.name} is splashed by your acid!"))
            if tmp:
                events.append(DamageEvent(target=mon.id, amount=tmp,
                                          damage_type=DamageType.ACID,
                                          source=hero.id))
    # AD_STON / AD_ENCH and the "still a monster" (polymorph) branch are
    # deferred with those systems.
    return events


# ------------------------------------------------------------
# The main entry point (C: mattacku)
# ------------------------------------------------------------

def mattacku(world: World, mon_id: str, rng, midnight: bool = False) -> List[Event]:
    """The monster attacks the hero (C: mattacku).

    Runs the monster's full attack sequence against the hero and returns
    the list of event *intents* (messages, damage, statuses).  It does
    NOT mutate any state -- the pure core (``rules.process_events``)
    applies the returned events.  Monsters without a ``PerMonst`` type
    (``mon.mdata is None``) are not handled here; they use the simple
    melee path in ``step``.
    """
    mon = world.actors[mon_id]
    hero = world.hero
    if mon.mdata is None or not mon.alive or not hero.alive:
        return []
    mdat: PerMonst = mon.mdata

    # hit differential (C: mattacku): AC + 10 + monster level, -2 if the
    # monster is trapped.  No LOS / Invis / displacement in the runtime,
    # so the "can't see you" and "multi-strike" adjustments are omitted.
    tmp = hero.ac + 10 + mdat.mlevel
    if is_stuck(mon):
        tmp -= 2
    if tmp <= 0:
        tmp = 1

    events: List[Event] = []
    prev = [M_ATTK_MISS] * NATTK
    # projected hero hp, so we stop producing attacks once the hero is
    # down (C stops the loop when the hero dies; here damage is applied
    # later, so we track it ourselves)
    hero_hp = hero.hp

    for i in range(NATTK):
        if hero_hp <= 0:
            break
        mattk = getmattk(mon, i, prev)
        aatyp = mattk.aatyp
        if aatyp in (AT_NONE, AT_BOOM):
            continue
        if distance_atk_type(aatyp):
            # spit / breath / magic / gaze are not ported yet (STUBs)
            continue
        if aatyp == AT_EXPL:
            events += explmu(world, mon, hero, mattk, rng)
            break  # an explosion ends the attack sequence
        if aatyp == AT_ENGL:
            continue  # swallowing is a STUB
        if aatyp == AT_HUGS:
            # automatic only if the previous two attacks both hit (C)
            if not (i >= 2 and prev[i - 1] == M_ATTK_HIT
                    and prev[i - 2] == M_ATTK_HIT):
                continue
        if aatyp == AT_KICK and mtrapped_in_pit(mon):
            continue

        j = _rnd(rng, 20 + i)
        if tmp > j:
            prev[i] = M_ATTK_HIT
            hit_events, dmg = hitmu(world, mon, hero, mattk, rng, midnight)
            events += hit_events
            hero_hp -= dmg
        else:
            prev[i] = M_ATTK_MISS
            events += missmu(mon, mattk, nearmiss=(tmp == j))

    return events


# ------------------------------------------------------------
# STUBs -- the C API surface, filled by the named ports
# ------------------------------------------------------------

def gulpmu(world: World, mon: Monster, hero: Monster, mattk: Attack,
           rng) -> List[Event]:
    """STUB (C: gulpmu): the monster swallows the hero (or digests him
    if already swallowed).  Needs the swallow machinery (u.uswallow /
    u.ustuck / u.uswldtim) -- the mon.c / swallow port."""
    raise NotImplementedError("gulpmu: swallowing is not ported yet")


def expels(mon: Monster, hero: Monster, mdat: PerMonst,
           message: bool = True) -> List[Event]:
    """STUB (C: expels): the swallower releases the hero.  Needs the
    swallow machinery -- the mon.c / swallow port."""
    raise NotImplementedError("expels: swallowing is not ported yet")


def gulp_blnd_check(world: World, mon: Monster, hero: Monster) -> bool:
    """STUB (C: gulp_blnd_check): whether an engulfing blindness should
    take effect right now (e.g. when the blindfold comes off).  Needs
    the swallow machinery -- the mon.c / swallow port."""
    raise NotImplementedError("gulp_blnd_check: swallowing is not ported yet")


def gazemu(world: World, mon: Monster, hero: Monster, mattk: Attack,
           rng) -> List[Event]:
    """STUB (C: gazemu): the monster's gaze attack.  Needs line-of-sight,
    stone resistance and polymorph -- the vision / polymorph ports."""
    raise NotImplementedError("gazemu: gazes are not ported yet")


def doseduce(world: World, mon: Monster, hero: Monster,
             rng) -> List[Event]:
    """STUB (C: doseduce): the seduction sequence (the nymph / amorous
    demon undresses and drains the hero).  Needs equipment, money and
    alignment -- the do_wear / money / align ports."""
    raise NotImplementedError("doseduce: seduction is not ported yet")


def mayberem(mon: Monster, hero: Monster, item, what: str) -> None:
    """STUB (C: mayberem): the seducer tries to remove a piece of the
    hero's armor.  Needs the equipment machinery -- the do_wear port."""
    raise NotImplementedError("mayberem: seduction is not ported yet")


def summonmu(mon: Monster, youseeit: bool, rng) -> List[Event]:
    """STUB (C: summonmu): a demon or were-creature calls for help.
    Needs ``msummon`` / ``were_summon``, night and Inhell -- the mon.c
    port."""
    raise NotImplementedError("summonmu: summoning is not ported yet")


def u_slip_free(mon: Monster, mattk: Attack) -> bool:
    """STUB (C: u_slip_free): whether the hero's greased / slippery
    clothing sheds a hug / wrap attack.  Needs the equipment machinery."""
    raise NotImplementedError("u_slip_free: equipment is not ported yet")


def magic_negation(mon: Monster) -> int:
    """STUB (C: magic_negation): how much the hero's armor / protection
    negates an incoming magic attack.  Needs the equipment / artifact
    machinery."""
    raise NotImplementedError("magic_negation: equipment is not ported yet")


def mon_avoiding_this_attack(mon: Monster, attkidx: int) -> bool:
    """STUB (C: mon_avoiding_this_attack): whether the monster is
    avoiding a particular attack because it has seen the hero resist
    it.  Needs the ``m_seenres`` bookkeeping -- the mon.c port."""
    raise NotImplementedError("mon_avoiding_this_attack: not ported yet")


def ranged_attk_available(mon: Monster) -> bool:
    """STUB (C: ranged_attk_available): whether the monster has a range
    attack it will actually use.  Needs the ``m_seenres`` bookkeeping."""
    raise NotImplementedError("ranged_attk_available: not ported yet")


def cloneu(world: World, mon: Monster, rng) -> Optional[str]:
    """STUB (C: cloneu): a gelatinous cube splits, leaving a clone.
    Needs the monster-spawn machinery -- the mon.c port.  Returns the
    new monster's id, or None."""
    raise NotImplementedError("cloneu: monster spawning is not ported yet")


def u_slow_down(hero: Monster) -> List[Event]:
    """STUB (C: u_slow_down): the hero's intrinsic speed is taken away.
    Needs the ability / speed system."""
    raise NotImplementedError("u_slow_down: the speed system is not ported yet")
