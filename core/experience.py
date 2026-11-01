"""Experience & leveling system (port of src/exper.c + the newhp half of
src/attrib.c).

The XP the hero gains from kills, the level thresholds, the level-up
(HP / Pw / level + the welcome message) and the level-loss (drain) path.
Everything is a pure function over ``World`` (plus an injected ``rng``
where a draw is made) that mutates the hero's bookkeeping fields
(``uexp`` / ``urexp`` / ``ulevel`` / ``ulevelmax`` / ``ulevelpeak`` /
``uhpinc`` / ``uen*`` / ``hp`` / ``max_hp``) and returns the hero-facing
``MessageEvent``s (C's plines).  The XP *gain* itself is silent, as in C
(more_experienced sets no pline, only the botl refresh -- the status line
redraws every turn here, so nothing is emitted).

The 5.0 experience system differs from 3.6 in one structural way this
port follows: ``struct permonst`` has no ``mexp`` column -- the XP of a
kill is COMPUTED from the monster's instance level (``m_lev``), effective
AC, speed and attack table by ``kill_experience`` (the C ``experience()``
in exper.c), not read from a table value.

C provenance per function (all in src/exper.c unless noted):

- ``newuexp``            C ``newuexp(lev)`` -- the "exp needed to reach
                         level `lev`" threshold (per-level, NOT
                         cumulative);
- ``kill_experience``    C ``experience(mtmp, nk)`` -- the full kill-XP
                         formula (base 1 + m_lev^2, the AC / speed /
                         attack / damage bonuses, extra_nasty, m_lev > 8,
                         the mail-daemon 1-XP case);
- ``more_experienced``   C ``more_experienced(exper, rexp)`` -- the XP
                         accumulation (``uexp += exper``,
                         ``urexp += 4*exper + rexp``);
- ``newexplevel``        C ``newexplevel()`` -- the AD&D-style at-most-one
                         level per call-site check;
- ``pluslvl``            C ``pluslvl(incr)`` -- the level-up (newhp / newpw
                         at the OLD level, the uexp carry, the welcome
                         pline, ulevelmax / ulevelpeak);
- ``newhp``              C ``newhp()`` (src/attrib.c) -- the HP-per-level
                         increment (the draw-free demo base + CON table,
                         PLAN-EXPERIENCE.md decision 5);
- ``init_experience``    the init uhpinc[0] record (C: the level-0 newhp
                         call in u_init.c);
- ``grant_kill_xp``      the kill-path hook (C: the ``tmp =
                         experience(mtmp, nk); more_experienced(tmp, 0);
                         newexplevel();`` of the mon.c ``mkill`` kill
                         wrapper -- 5.0's ``mondead`` does NOT grant XP,
                         the grant stays in the kill wrapper for
                         hero-caused kills);
- ``losexp``             C ``losexp(drainer)`` -- the level-loss / drain
                         path (the HP / Pw / XP reduction, the level-1 +
                         drainer death, the divine-anger level-1 reset).

Simplifications (documented, not bugs -- PLAN-EXPERIENCE.md §4 / §5):

- ``m_lev`` is PINNED to ``mdata.mlevel`` at spawn (not the C ``adj_lev``
  roll) so world generation stays draw-free; the roll lands with the
  makemon port.
- The kill-count decay of C ``experience()`` (the mrevived / mcloned
  halving bands) is out -- the demo has no revival / cloning, so ``nk`` is
  always 1 and the branch is omitted (the parameter is kept for the C API
  shape).
- ``find_mac`` (C) -> the computed ``core.worn.uac`` (the demo monsters
  wear nothing, so effective AC == base ac; the computed value keeps it
  correct the day monsters carry gear).
- ``newhp`` is draw-free (the C role/race hpadv rnd lands with the
  role-selection port); the demo hero's CON 12 gives the +0 CON row.
- The level-up Pw gain reuses ``core.energy.newpw`` (the committed, tested
  module -- its low-level branch is C's exactly); the C role/race enadv +
  enermod formula is deferred.
- No ``resists_drli`` bail-out (no DRLI-resistance source in the demo
  hero) -- the losexp check is a documented no-op.
- The ``adjabil`` intrinsic grants (the role/race role_abil / race_abil
  tables) are skipped on both pluslvl and losexp (no intrinsic system in
  the demo; the prop-system port, PLAN-ARMOR.md decision 7).
- The livelog / rank-achievement / SoundAchievement of pluslvl / losexp
  and the C ``flags.beginner`` / status hilites of more_experienced have
  no pyhack machinery -- the demo message is the welcome / goodbye pline
  only.
- The C ``LONG_MAX`` wraparound caps in more_experienced (and the
  post-MAXULEV 1200 / 600 throttles in newhp / newpw) are no-ops for
  Python ints / unreachable in the demo.
"""
from __future__ import annotations

from typing import List, Optional

from .energy import newpw
from .events import DeathEvent, Event, MessageEvent
from .mondata import extra_nasty
from .monst import (AD_BLND, AD_DRLI, AD_PHYS, AD_SLIM, AD_STON, AD_WRAP,
                    AT_BUTT, AT_MAGC, AT_WEAP, NORMAL_SPEED,
                    PM_MAIL_DAEMON, S_EEL)
from .types import MAXULEV, Monster, World
from .worn import uac


# ------------------------------------------------------------
# The level threshold (C: newuexp)
# ------------------------------------------------------------

def newuexp(lev: int) -> int:
    """C: newuexp(lev) -- the experience needed to REACH level ``lev``
    (the threshold crossed to go from level ``lev`` to ``lev + 1``).

    Per-level, NOT cumulative: newuexp(1) = 20 (L1 -> L2),
    newuexp(2) = 40 (L2 -> L3), ... The uexp counter persists across
    level-ups (the overflow past the NEXT threshold is forfeited by
    pluslvl, the rest carries).
    """
    if lev < 1:  # for newuexp(u.ulevel - 1) when u.ulevel is 1
        return 0
    if lev < 10:
        return 10 * (1 << lev)
    if lev < 20:
        return 10000 * (1 << (lev - 10))
    return 10000000 * (lev - 19)


# ------------------------------------------------------------
# The kill-XP formula (C: experience)
# ------------------------------------------------------------

def kill_experience(world: World, mon: Monster, nk: int = 1) -> int:
    """C: experience(mtmp, nk) -- the XP for killing ``mon``.

    ``nk`` is the per-type kill count (the mrevived / mcloned decay
    bands); it is kept for the C API shape -- the demo has no revival /
    cloning, so ``nk`` is always 1 and the decay branch is omitted
    (PLAN-EXPERIENCE.md §4).  Draw-free: a pure function of the monster's
    PerMonst type and instance level.

    The AC bonus reads the EFFECTIVE armor class (C ``find_mac`` -> the
    computed ``core.worn.uac``), never the base body AC.
    """
    xp = 1 + mon.m_lev * mon.m_lev
    ptr = mon.mdata
    if ptr is None:
        # a flat-stat monster (no PerMonst): the base only
        return xp

    # For higher AC values, give extra experience (C: find_mac < 3)
    i = uac(world, mon)
    if i < 3:
        xp += (7 - i) * (2 if i < 0 else 1)

    # For very fast monsters, give extra experience (C: mmove > NORMAL_SPEED)
    if ptr.mmove > NORMAL_SPEED:
        xp += 5 if ptr.mmove > 3 * NORMAL_SPEED // 2 else 3

    # For each "special" attack type give extra experience
    for a in ptr.mattk:
        if a.aatyp > AT_BUTT:
            if a.aatyp == AT_WEAP:
                xp += 5
            elif a.aatyp == AT_MAGC:
                xp += 10
            else:
                xp += 3

    # For each "special" damage type give extra experience
    for a in ptr.mattk:
        if AD_PHYS < a.adtyp < AD_BLND:
            xp += 2 * mon.m_lev
        elif a.adtyp in (AD_DRLI, AD_STON, AD_SLIM):
            xp += 50
        elif a.adtyp != AD_PHYS:
            xp += mon.m_lev
        # extra heavy damage bonus
        if a.damd * a.damn > 23:
            xp += mon.m_lev
        # the eel's wrap vs a non-amphibious hero (C: && !Amphibious --
        # the demo hero is never amphibious, a documented no-op)
        if a.adtyp == AD_WRAP and ptr.mlet == S_EEL:
            xp += 1000

    # For certain "extra nasty" monsters, give even more (C: extra_nasty
    # is the M2_NASTY flag, mondata.h)
    if extra_nasty(ptr):
        xp += 7 * mon.m_lev

    # For higher level monsters, an additional bonus is given
    if mon.m_lev > 8:
        xp += 50

    # Mail daemons put up no fight (C: MAIL_STRUCTURES, always in 5.0)
    if ptr.pmidx == PM_MAIL_DAEMON:
        xp = 1

    return xp


# ------------------------------------------------------------
# The XP accumulation (C: more_experienced)
# ------------------------------------------------------------

def more_experienced(world: World, exper: int, rexp: int = 0) -> None:
    """C: more_experienced(exper, rexp) -- add ``exper`` XP to the hero.

    ``uexp += exper`` (the leveling XP) and ``urexp += 4*exper + rexp``
    (the SCORE XP; a kill passes rexp = 0).  Silent -- C emits no message
    on XP gain (only the botl refresh, which the status line covers here).

    The C ``LONG_MAX`` wraparound cap is a no-op for Python ints; C's
    ``flags.beginner`` reset has no pyhack machinery (documented).
    """
    hero = world.hero
    hero.uexp += exper
    hero.urexp += 4 * exper + rexp


# ------------------------------------------------------------
# The level check (C: newexplevel)
# ------------------------------------------------------------

def newexplevel(world: World, rng) -> List[Event]:
    """C: newexplevel -- make experience gaining similar to AD&D: at most
    ONE level per call-site (the comment in exper.c says so explicitly).

    Levels up when ``uexp >= newuexp(ulevel)`` (and below MAXULEV)."""
    hero = world.hero
    if hero.ulevel < MAXULEV and hero.uexp >= newuexp(hero.ulevel):
        return pluslvl(world, True, rng)
    return []


# ------------------------------------------------------------
# The HP-per-level increment (C: newhp, src/attrib.c)
# ------------------------------------------------------------

def _con_bonus(con: int) -> int:
    """C: the CON table of newhp (src/attrib.c) -- the constitution
    contribution to the per-level HP increment."""
    if con <= 3:
        return -2
    if con <= 6:
        return -1
    if con <= 14:
        return 0
    if con <= 16:
        return 1
    if con == 17:
        return 2
    if con == 18:
        return 3
    return 4


def newhp(world: World) -> int:
    """C: newhp (src/attrib.c) -- the HP increment for a level-up.

    The DEMO form (PLAN-EXPERIENCE.md decision 5): a draw-free fixed base
    2 + the C CON table (the demo hero's CON 12 -> +0 -> 2).  C's
    role/race hpadv rnd (the Wizard row: 0 + rnd(8) below xlev 12,
    1 + rnd(0) above -- verified in src/role.c) lands with the
    role-selection port.

    Records the increment in ``uhpinc[ulevel]`` (the OLD level, before
    the caller increments it -- C: ``u.uhpinc[u.ulevel] = hp``) and
    returns it.  The post-MAXULEV throttle (the 1200 cap) is unreachable
    in the demo and omitted (documented).
    """
    hero = world.hero
    hp = 2 + _con_bonus(hero.ucon)
    if hp <= 0:
        hp = 1
    if hero.ulevel < MAXULEV:
        hero.uhpinc[hero.ulevel] = hp
    return hp


def init_experience(world: World) -> None:
    """C: the level-0 ``newhp`` call of u_init.c -- record ``uhpinc[0]``
    (the init / level-0 increment).  Draw-free, no message.

    Behaviourally inert in the demo today (a level-1 losexp does not
    subtract HP in C, and it feeds the life-saving minimum) -- kept for
    C fidelity (PLAN-EXPERIENCE.md risk 4).
    """
    hero = world.hero
    hero.uhpinc[0] = max(1, 2 + _con_bonus(hero.ucon))


# ------------------------------------------------------------
# The level-up (C: pluslvl)
# ------------------------------------------------------------

def pluslvl(world: World, incr: bool, rng) -> List[Event]:
    """C: pluslvl(incr) -- raise the hero a level.

    ``incr=True`` is the incremental-experience path (the uexp carry: the
    overflow past the NEXT threshold is forfeited); ``incr=False`` is the
    potion-of-gain-level / wraith-corpse / ``#levelchange`` path (no demo
    caller this round -- implemented and unit tested directly,
    PLAN-EXPERIENCE.md decision 10).

    ``newhp()`` and ``newpw()`` are evaluated at the OLD level, as in C.
    The C ``adjabil`` intrinsic grant and the livelog / rank-achievement
    are skipped in the demo (no intrinsic system; PLAN-EXPERIENCE.md
    decision 11).
    """
    hero = world.hero
    events: List[Event] = []
    if not incr:
        events.append(MessageEvent("You feel more experienced."))

    # increase hit points (C: newhp at the OLD level; records uhpinc[old])
    hpinc = newhp(world)
    hero.hp += hpinc
    hero.max_hp += hpinc

    # increase spell power (C: newpw at the OLD level -- the ONE draw of
    # the whole XP path on the first, L1 -> L2, level-up)
    eninc = newpw(hero.ulevel, rng)
    # C: newpw() records the increment it grants at the OLD level
    # ("remember increment; future level drain could take it away
    # again") -- losexp() subtracts it on a level loss
    if hero.ulevel < MAXULEV:
        hero.ueninc[hero.ulevel] = eninc
    hero.uenmax += eninc
    if hero.uenmax > hero.uenpeak:
        hero.uenpeak = hero.uenmax
    hero.uen += eninc

    # increase level (unless already maxxed)
    if hero.ulevel < MAXULEV:
        # increase experience points to reflect the new level
        if incr:
            tmp = newuexp(hero.ulevel + 1)
            if hero.uexp >= tmp:
                hero.uexp = tmp - 1  # the overflow past the next level
        else:
            hero.uexp = newuexp(hero.ulevel)
        hero.ulevel += 1
        # C: the welcome pline -- "back" only when NOT a new high
        # ((u.ulevelmax < u.ulevel) ? "" : "back ")
        back = "" if hero.ulevelmax < hero.ulevel else "back "
        events.append(MessageEvent(
            f"Welcome {back}to experience level {hero.ulevel}."))
        if hero.ulevelmax < hero.ulevel:
            hero.ulevelmax = hero.ulevel
        # C: adjabil(u.ulevel - 1, u.ulevel) -- the intrinsic grants are
        # skipped in the demo (decision 11)
        if hero.ulevel > hero.ulevelpeak:
            hero.ulevelpeak = hero.ulevel
    return events


# ------------------------------------------------------------
# The level-loss / drain (C: losexp)
# ------------------------------------------------------------

def losexp(world: World, drainer: Optional[str]) -> List[Event]:
    """C: losexp(drainer) -- the level-loss (drain) path.

    ``drainer`` is the cause-of-death string (the C killer string, e.g.
    the name of the monster that drained the hero).  ``drainer=None`` is
    divine anger -- a level-1 character resets to 0 XP without losing a
    level (not fatal).  ``drainer="#levelchange"`` is the wizard-mode
    override (never fatal); the ``#levelchange`` command lands with the
    wizard-mode port (PLAN-EXPERIENCE.md §5.3).

    C's ``resists_drli`` bail-out is a documented no-op in the demo (no
    DRLI-resistance source; decision 7).  A level-1 + drainer loss is
    FATAL: the hero dies through the same death bookkeeping as
    ``apply_damage`` (alive=False + DeathEvent(by=drainer)), which
    ``step._finish`` turns into the GameOverEvent.
    """
    hero = world.hero
    events: List[Event] = []
    drainer_eff = None if drainer == "#levelchange" else drainer

    # the level-loss message (C: pline("%s level %d.", Goodbye(), u.ulevel));
    # suppressed for the level-1 divine-anger reset (not fatal)
    if hero.ulevel > 1 or drainer_eff:
        events.append(MessageEvent(f"Goodbye level {hero.ulevel}."))

    if hero.ulevel > 1:
        hero.ulevel -= 1
        # C: adjabil(u.ulevel + 1, u.ulevel) removes intrinsics -- no
        # intrinsic system in the demo (decision 11)
        old_uhpmax = hero.max_hp
        # C: minuhpmax(10) -- the same minimum as life-saving
        uhpmin = max(hero.ulevel, 10)
        num = hero.uhpinc[hero.ulevel]
        hero.max_hp -= num
        if hero.max_hp < uhpmin:
            hero.max_hp = uhpmin
        # C: uhpmax must not go UP through losexp (it may have been
        # reduced by strength loss / a fire trap / Death)
        if hero.max_hp > old_uhpmax:
            hero.max_hp = old_uhpmax
        hero.hp -= num
        if hero.hp < 1:
            hero.hp = 1
        elif hero.hp > hero.max_hp:
            hero.hp = hero.max_hp
        # the Pw half (C: the ueninc[u.ulevel] reduction)
        num = hero.ueninc[hero.ulevel]
        hero.uenmax -= num
        if hero.uenmax < 0:
            hero.uenmax = 0
        hero.uen -= num
        if hero.uen < 0:
            hero.uen = 0
        elif hero.uen > hero.uenmax:
            hero.uen = hero.uenmax
        if hero.uexp > 0:
            hero.uexp = newuexp(hero.ulevel) - 1
    else:  # u.ulevel == 1
        if drainer_eff:
            # C: done(DIED) -- the hero dies to the drainer (the apply_
            # damage death bookkeeping; step._finish makes the GameOver)
            hero.alive = False
            events.append(DeathEvent(target=hero.id, by=drainer_eff))
            events.append(MessageEvent("💀 You are dead!"))
        else:
            # C: divine anger (drainer == NULL) -- reset the XP to 0, no
            # level change
            hero.uexp = 0
    return events


# ------------------------------------------------------------
# The kill-XP hook (C: the mkill kill path, mon.c)
# ------------------------------------------------------------

def grant_kill_xp(world: World, mon: Monster, rng) -> List[Event]:
    """The kill-XP hook -- the body ``rules.apply_damage`` calls when a
    NON-HERO monster dies to the hero (``source == world.hero.id``):
    C's ``tmp = experience(mtmp, nk); more_experienced(tmp, 0);
    newexplevel();`` of the mon.c ``mkill`` kill wrapper.

    Draw-free except the level-up: the ONLY draw of the whole XP path is
    the ``energy.newpw`` on the FIRST (L1 -> L2) level-up
    (PLAN-EXPERIENCE.md decision 6 / risk 1).  Returns the level-up
    ``MessageEvent``s (empty when no level is gained).
    """
    xp = kill_experience(world, mon)
    more_experienced(world, xp)
    return newexplevel(world, rng)
