"""Monster genesis (port of src/makemon.c).

`makemon()` is one function, but it is a funnel: a dozen helpers decide
*which* monster, *where*, *how strong* and *in what mood*.  This module
is the funnel and its helpers; the placement half (`goodpos` / `enexto`)
lives in core.place because teleportation and the level change need it
too, and the per-type vitals live on `World.mon_state`
(core.mondata.MonState).

C provenance (all src/makemon.c unless noted):

  makemon()                      the funnel
  makemon_rnd_goodpos()          rnd_goodpos()
  rndmonst() / rndmonst_adj()    the weighted reservoir sample
  uncommon()                     the "rare species" filter
  align_shift() / temperature_shift()
                                 the two level-flavour weight adjustments
  mk_gen_ok()                    gen_ok()
  init_mongen_order() / cmp_init_mongen_order() / mclass_maxf[]
                                 MongenOrder
  mkclass() / mkclass_aligned()  the per-class weighted pick
  adj_lev()                      the instance level
  newmonhp() / monhp_per_lvl() / golemhp()
                                 the hit points
  mbirth_limit()                 the population cap
  propagate()                    World.mon_state.propagate() (core.mondata)
  peace_minded() / set_malign()  the mood
  mongets() / mkmonmoney()       the monster's pocket
  goodpos() / enexto()           core.place (src/teleport.c)

Draw order (PLAN-MAKEMON.md decision 4): position first (when the caller
asked for "anywhere"), then the type, then the hit points, then the
gender, then the mood, then the inventory.  The level's rng stream is
shared with the generator, so a reordering silently reshuffles every
later draw of the level -- keep C's order.

What the caller gets back is C's `struct monst *` or NULL: `makemon()`
returns `Optional[Monster]`, and C None (no monster) is a *normal*
result -- a level with no legal square for the requested type, a
genocided species, a population that has gone extinct -- so it never
raises (PLAN-MAKEMON.md decision 1).

STUBs (announced here, each with the C it waits for):

  - ``m_initweap()`` (C: 160-572) and ``m_initinv()`` (588-833): the
    400-line "which weapon would this species prefer" switch chains and
    the per-class extras (jelly treasure, leprechaun gold, nymph items).
    ``mongets()`` (give one named otyp) and ``mkmonmoney()`` (a purse)
    are ported, so the *mechanism* is in place; the species tables are
    PLAN-MAKEMON.md phase E.
  - ``m_initgrp()`` / ``m_initsgrp()`` / ``m_initlgrp()``: monster
    groups (soldier squads, orc bands) -- phase F.  The generator passes
    MM_NOGRP meanwhile, so the flag is honoured, not faked.
  - ``set_mimic_sym()``: a mimic needs the display glyph machinery, and
    ``hideunder()`` (a spider / eel under a wall) needs concealment.
  - ``grow_up()`` / ``clone_mon()`` / ``create_critters()`` /
    ``unmakemon()``: phase F.
  - ``christen_monst()`` and the "A kobold appears!" message: there is
    no monster message layer yet, so MM_NOMSG is effectively always on.
  - the ``mtmp->cham`` (shapechanger), ``iswiz`` and ``mextra`` halves:
    no polymorph, no quest, no priests / shopkeepers yet, so MM_EPRI /
    MM_ESHK / MM_EDOG / MM_EMIN / MM_EGD are accepted and ignored.

Deliberate divergences (documented, not bugs):

  - ``World.hero_align`` is A_NEUTRAL and there is no alignment system,
    so ``peace_minded()`` keeps C's shape but its inputs are constant
    (PLAN-MAKEMON.md divergence 1): an aligned monster is hostile to the
    neutral hero, a neutral one gets C's co-aligned chance.
  - no Inhell / In_sokoban / quest / endgame level predicates exist:
    every such branch keeps the temperate-dungeon default and says so.
  - a long worm is one monster (no segments), so MM_NOTAIL is accepted
    and ignored (divergence 3).
  - the sparse monster table is a *filter*: a row that is not
    implemented (MONS[mndx] is None) is skipped by rndmonst_adj() and
    mkclass(), because the species effectively does not exist yet
    (PLAN-MAKEMON.md §7, "the sparse table").
"""

from __future__ import annotations

from typing import Dict, List, Optional

from . import rules
from .hacklib import sgn
from .mondata import (always_hostile, always_peaceful, is_armed, is_female,
                      is_male, is_minion, is_neuter, is_placeholder,
                      is_rider, set_mon_data)
from .monst import (A_NONE, G_FREQ, G_GENOD, G_GONE, G_HELL, G_NOGEN, G_UNIQ,
                    LOW_PM, M2_LORD, M2_PRINCE, M3_CLOSE, M3_COVETOUS,
                    M3_WAITFORU, M3_WAITMASK, MAXMCLASSES, MONS, MS_GUARDIAN,
                    MS_LEADER, MS_NEMESIS, PM_ERINYS, PM_GRAY_DRAGON,
                    PM_IRON_GOLEM, PM_NAZGUL, PM_STONE_GOLEM,
                    PM_WIZARD_OF_YENDOR, S_BAT, S_DEMON, S_EEL, S_ELEMENTAL,
                    S_JABBERWOCK, S_LEPRECHAUN, S_LICH, S_LIGHT, S_MIMIC,
                    S_NYMPH, S_ORC, S_SNAKE, S_SPIDER, S_UNICORN, SPECIAL_PM,
                    PerMonst, is_golem, monname, monsndx)
from .place import enexto_core, goodpos
from .types import (GP_AVOID_MONPOS, GP_CHECKSCARY, MM_IGNOREWATER, Map,
                    MmFlags, Monster, NO_MM_FLAGS, Pos, World)

# C: global.h MAXMONNO -- how many of one species may be born before it
# goes extinct (see mbirth_limit / MonState.propagate).
MAXMONNO = 120

# C: hack.h STRAT_* -- the strategy bits a monster's M3_ flags set.
STRAT_NONE = 0x0
STRAT_WAITFORU = 0x1
STRAT_CLOSE = 0x2
STRAT_WAITMASK = STRAT_WAITFORU | STRAT_CLOSE
STRAT_APPEARMSG = 0x4


# ------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------

def _mons(mndx: int) -> Optional[PerMonst]:
    """mons[mndx], or None for a table row the port has not filled in."""
    return MONS[mndx]


def monmin_difficulty(levdif: int) -> int:
    """C: monst.h -- the weakest monster a level may generate."""
    return levdif // 6


def monmax_difficulty(levdif: int, ulevel: int) -> int:
    """C: monst.h -- the strongest monster a level may generate."""
    return (levdif + ulevel) // 2


def is_home_elemental(ptr: PerMonst) -> bool:
    """C: is_home_elemental -- an elemental on its own plane.  pyhack has
    no elemental planes and no In_endgame(), so this is False (which is
    what the C main dungeon answers too)."""
    del ptr
    return False


# ------------------------------------------------------------
# Which monster: the selection half (C: uncommon .. mkclass_aligned)
# ------------------------------------------------------------

def uncommon(world: World, mndx: int) -> bool:
    """Is this species excluded from random creation (C: uncommon)?

    Never-generated and unique species, species that are genocided or
    extinct (G_GONE), and the hell-only ones on a temperate level.  C's
    Inhell half of the test has no pyhack counterpart -- there is no
    Gehennom -- so the temperate-dungeon answer is the whole answer.
    """
    ptr = MONS[mndx]
    if ptr is None:
        return True
    if ptr.geno & (G_NOGEN | G_UNIQ):
        return True
    if world.mon_state.mvitals[mndx].mvflags & G_GONE:
        return True
    return (ptr.geno & G_HELL) != 0


def align_shift(ptr: PerMonst) -> int:
    """C: align_shift -- the level-alignment contribution to a species'
    creation weight.  STUB: the number is computed from the *dungeon's*
    alignment (AM_NONE in the unported dungeon topology), which is 0;
    the C formula is kept in the comment so the fill-in is arithmetic.

        AM_LAWFUL:  (ptr->maligntyp + 20) / (2 * ALIGNWEIGHT)
        AM_NEUTRAL: (20 - abs(ptr->maligntyp)) / ALIGNWEIGHT
        AM_CHAOTIC: (-(ptr->maligntyp - 20)) / (2 * ALIGNWEIGHT)
    """
    del ptr
    return 0


def temperature_shift(world: World, ptr: PerMonst) -> int:
    """C: temperature_shift -- a species that resists the level's
    temperature is generated more often.  STUB: levels have no
    temperature flag yet (svl.level.flags.temperature), so 0."""
    del world, ptr
    return 0


def rndmonst(world: World, rng) -> Optional[PerMonst]:
    """A random common monster (C: rndmonst)."""
    return rndmonst_adj(world, rng, 0, 0)


def rndmonst_adj(world: World, rng, minadj: int,
                 maxadj: int) -> Optional[PerMonst]:
    """A random monster for this level, its difficulty band widened by
    minadj / maxadj (C: makemon.c#rndmonst_adj).

    The weighted reservoir sample is C's, draw for draw: for every
    candidate species, `rn2(totalweight) < weight` decides whether it
    replaces the current pick, so the earlier species' better odds are
    exactly cancelled by the later ones' chances to steal the slot.

    Returns None when nothing is eligible -- C's "no monster", which the
    callers treat as a normal outcome.
    """
    zlevel = rules.level_difficulty(world)
    minmlev = monmin_difficulty(zlevel) + minadj
    maxmlev = monmax_difficulty(zlevel, world.hero_ulevel) + maxadj

    totalweight = 0
    selected_mndx = -1
    for mndx in range(LOW_PM, SPECIAL_PM):
        ptr = MONS[mndx]
        if ptr is None:
            continue                       # a row the port lacks yet
        if ptr.difficulty < minmlev or ptr.difficulty > maxmlev:
            continue
        if uncommon(world, mndx):
            continue
        weight = (ptr.geno & G_FREQ) + align_shift(ptr) \
            + temperature_shift(world, ptr)
        if weight < 0 or weight > 127:
            weight = 0                     # C: impossible("bad weight")
        if weight > 0:
            totalweight += weight
            if rng.rn2(totalweight) < weight:
                selected_mndx = mndx

    if selected_mndx < 0 or uncommon(world, selected_mndx):
        return None
    return MONS[selected_mndx]


class MongenOrder:
    """C: mongen_order[] + mclass_maxf[] (makemon.c init_mongen_order).

    Every implemented species ordered by (mlet, difficulty), so that
    mkclass() can find one class's species as a contiguous run (C's
    "Rule #1: monsters of a given class are contiguous"), plus the
    highest G_FREQ of each class -- 0 means "this class has no
    generatable species", which is what mkclass() uses to know whether
    the whole class must borrow a frequency of 1.

    Two documented divergences: only implemented rows are sorted (a
    missing row has no difficulty to sort by; it is skipped by
    mkclass() anyway), and the sort is Python's stable one where C uses
    qsort -- the same rule as core.mklev.sort_rooms.
    """

    def __init__(self) -> None:
        order: List[int] = [i for i in range(LOW_PM, SPECIAL_PM)
                            if MONS[i] is not None]
        maxf = [0] * MAXMCLASSES
        for mndx in order:
            ptr = MONS[mndx]
            assert ptr is not None      # narrowed by the comprehension
            freq = ptr.geno & G_FREQ
            if freq > maxf[ptr.mlet]:
                maxf[ptr.mlet] = freq
        # C: (mons[i].difficulty | mons[i].mlet << 8) -- the class in
        # the high byte, the difficulty in the low one
        order.sort(key=lambda i: _order_key(MONS[i]))
        self.order = order
        self.maxf = maxf


def _order_key(ptr: Optional[PerMonst]) -> int:
    assert ptr is not None
    return ptr.difficulty | (int(ptr.mlet) << 8)


_MONGEN_ORDER: Optional[MongenOrder] = None


def mongen_order() -> MongenOrder:
    """The (lazily built, never mutated) generation order.

    C builds it once into a file-static array behind a boolean; pyhack
    keeps it in a module-level cache for the same reason -- it is a pure
    function of the frozen monster table, so it is table data, not game
    state (the same argument as DEFCHARS).
    """
    global _MONGEN_ORDER
    if _MONGEN_ORDER is None:
        _MONGEN_ORDER = MongenOrder()
    return _MONGEN_ORDER


def gen_ok(world: World, mndx: int, mvflagsmask: int,
           genomask: int) -> bool:
    """May mkclass() consider this species (C: mk_gen_ok)?

    Rejects the genocided / extinct ones (the mvflags mask), the ones
    whose geno bits collide with the caller's mask (unique, never
    generated, hell-only, ...), and the placeholders.
    """
    ptr = MONS[mndx]
    if ptr is None:
        return False
    if world.mon_state.mvitals[mndx].mvflags & mvflagsmask:
        return False
    if ptr.geno & genomask:
        return False
    if is_placeholder(ptr):
        return False
    # C: MAIL_STRUCTURES -- "special levels might ask for a random
    # demon type; reject this one"
    return not _is_mail_daemon(ptr)


def _is_mail_daemon(ptr: PerMonst) -> bool:
    """C: `ptr == &mons[PM_MAIL_DAEMON]` (the mail daemon is a joke
    monster that must never be a random pick)."""
    return ptr.pmnames[2] == "mail daemon"


def mkclass(world: World, rng, mclass: int,
            spc: int = 0) -> Optional[PerMonst]:
    """A random species of monster class `mclass` (C: mkclass), or None.

    `spc` is C's "special mons[].geno handling": the geno bits to ignore
    (G_NOGEN | G_UNIQ by default), plus G_IGNORE to also accept the
    genocided / extinct species.
    """
    return mkclass_aligned(world, rng, mclass, spc, A_NONE)


def mkclass_aligned(world: World, rng, mclass: int, spc: int,
                    atyp: int) -> Optional[PerMonst]:
    """mkclass() with an alignment restriction (C: mkclass_aligned).

    C's three assumptions, kept: a class is a contiguous run of the
    generation order; the run is in ascending difficulty; and a species
    past the level's difficulty is only accepted when nothing has been
    picked yet or the difficulty did not go up (so a class that starts
    above the level's band still yields its weakest members).  The
    weights skew towards the lower end at low experience levels: a
    species whose adjusted level exceeds twice the hero's gets one less
    chance than its frequency says.
    """
    mo = mongen_order()
    maxmlev = rules.level_difficulty(world) >> 1
    if mclass < 1 or mclass >= MAXMCLASSES:
        return None                        # C: impossible("bad class")
    zero_freq_for_entire_class = mo.maxf[mclass] == 0

    order = mo.order
    first = 0
    while first < len(order):
        row = MONS[order[first]]
        assert row is not None             # order holds implemented rows
        if row.mlet == mclass:
            break
        first += 1
    if first == len(order):
        return None                        # C: no such class implemented

    mv_mask: int = int(G_GONE)
    if spc & 0x8000:                       # C: G_IGNORE
        mv_mask = 0
        spc &= ~0x8000

    nums: Dict[int, int] = {}
    num = 0
    last = first
    while last < len(order):
        mndx = order[last]
        ptr = MONS[mndx]
        assert ptr is not None             # order holds implemented rows
        if ptr.mlet != mclass:
            break
        last += 1
        if atyp != A_NONE and sgn(ptr.maligntyp) != sgn(atyp):
            continue
        # C: traditionally ignored hell-only / never-in-hell; now mostly
        # honoured, but not for one species in nine (and always for the
        # liches).  There is no Gehennom here, so the temperate half of
        # the mask is the one that can apply.
        gn_mask = G_NOGEN | G_UNIQ
        if rng.rn2(9) or mclass == S_LICH:
            gn_mask |= G_HELL
        gn_mask &= ~spc
        if not gen_ok(world, mndx, mv_mask, gn_mask):
            continue
        # don't reject a too-strong monster if we have nothing yet, or
        # if it is no stronger than the previous candidate
        if num and ptr.difficulty > maxmlev:
            prev = MONS[order[last - 2]]
            assert prev is not None
            if ptr.difficulty > prev.difficulty and rng.rn2(2):
                break
        k = ptr.geno & G_FREQ
        if k == 0 and zero_freq_for_entire_class:
            k = 1
        if k > 0:
            too_high = adj_lev(world, ptr) > (world.hero_ulevel * 2)
            nums[mndx] = k + 1 - (1 if too_high else 0)
            num += nums[mndx]

    if not num:
        return None

    # C: for (num = rnd(num); first < last; first++)
    #        if ((num -= nums[MONSi(first)]) <= 0) break;
    num = rng.rnd(num)
    while first < last:
        mndx = order[first]
        num -= nums.get(mndx, 0)
        if num <= 0:
            break
        first += 1
    if first >= last or not nums.get(order[first], 0):
        return None
    return MONS[order[first]]


# ------------------------------------------------------------
# How strong: adj_lev / newmonhp / golemhp
# ------------------------------------------------------------

def adj_lev(world: World, ptr: PerMonst) -> int:
    """The monster's *actual* level on this level (C: makemon.c#adj_lev).

    Not to be confused with `ptr.mlevel`, the table value: adj_lev grows
    a species with the dungeon depth and with the hero's level, which is
    why a depth-12 goblin is worth more than a depth-1 one.  The result
    is stored on the instance as `Monster.m_lev`; never re-derive it
    from the table (PLAN-MAKEMON.md §7).
    """
    if ptr.pmidx == PM_WIZARD_OF_YENDOR:
        tmp = ptr.mlevel + world.mon_state.mvitals[ptr.pmidx].died
        return min(tmp, 49)
    if ptr.mlevel > 49:
        return 50                      # "special" demons / devils
    tmp = ptr.mlevel
    tmp2 = rules.level_difficulty(world) - tmp
    if tmp2 < 0:
        tmp -= 1                       # weaker than the level: drop one
    else:
        tmp += tmp2 // 5               # one per five of difference
    tmp2 = world.hero_ulevel - ptr.mlevel
    if tmp2 > 0:
        tmp += tmp2 // 4               # and one per four of hero level
    tmp2 = (3 * ptr.mlevel) // 2       # crude upper limit
    if tmp2 > 49:
        tmp2 = 49
    if tmp > tmp2:
        tmp = tmp2
    return tmp if tmp > 0 else 0


def golemhp(mndx: int) -> int:
    """A golem's fixed hit points (C: makemon.c#golemhp)."""
    table = {
        249: 20,   # C: PM_STRAW_GOLEM
        250: 20,   # C: PM_PAPER_GOLEM
        251: 30,   # C: PM_ROPE_GOLEM
        252: 60,   # C: PM_GOLD_GOLEM
        253: 40,   # C: PM_LEATHER_GOLEM
        254: 50,   # C: PM_WOOD_GOLEM
        255: 40,   # C: PM_FLESH_GOLEM
        256: 70,   # C: PM_CLAY_GOLEM
        PM_STONE_GOLEM: 100,
        258: 80,   # C: PM_GLASS_GOLEM
        PM_IRON_GOLEM: 120,
    }
    return table.get(mndx, 0)


def monhp_per_lvl(mon: Monster, rng) -> int:
    """How much HP one level of gain is worth to this monster (the
    level-drain / Stormbringer amount; C: makemon.c#monhp_per_lvl).

    Like newmonhp, but the home elementals are ignored and the riders
    use the plain d8.  No live call site yet: it lands with the mhitu
    AD_DRLI port (PLAN-EXPERIENCE.md / core.experience.losexp).
    """
    ptr = mon.mdata
    assert ptr is not None
    hp = rng.rnd(8)                    # default is d8
    if is_golem(ptr):
        mlev = ptr.mlevel or 1
        hp = golemhp(monsndx(ptr)) // mlev
    elif ptr.mlevel > 49:
        hp = 4 + rng.rnd(4)            # 5..8, arbitrary
    elif ptr.mlet == 30 and monsndx(ptr) >= PM_GRAY_DRAGON:
        # C: S_DRAGON; adult dragons roll 4..8 here
        hp = 4 + rng.rn2(5)
    elif not mon.m_lev:
        hp = rng.rnd(4)                # level 0 monsters use 1d4
    return hp


def newmonhp(world: World, rng, mon: Monster, mndx: int) -> None:
    """Set a new monster's instance level and hit points (C:
    makemon.c#newmonhp; newcham() uses it too).

    The order of the C tests matters: a golem's HP is a constant per
    species, a rider gets a deliberately low d(10,8) behind a high
    `m_lev`, a "special" monster (mlevel > 49) encodes its HP in the
    table level, an adult dragon rolls N*(4+d4), and everything else
    rolls N d8 with a floor of 2 (the "all ones" boost at the end).
    """
    ptr = MONS[mndx]
    assert ptr is not None
    basehp = 0

    mon.m_lev = adj_lev(world, ptr)
    if is_golem(ptr):
        mon.max_hp = mon.hp = golemhp(mndx)
    elif is_rider(ptr):
        # low HP but a high m_lev so they can attack well
        basehp = 10
        mon.max_hp = mon.hp = rng.d(basehp, 8)
    elif ptr.mlevel > 49:
        # "special" fixed-HP monster: the hit points are encoded in the
        # mlevel column (2 * (mlevel - 6))
        mon.max_hp = mon.hp = 2 * (ptr.mlevel - 6)
        mon.m_lev = mon.hp // 4        # approximation
    elif ptr.mlet == 30 and mndx >= PM_GRAY_DRAGON:
        # C: S_DRAGON; adult dragons roll N*(4+d4) (N*8 in the endgame,
        # which is not modelled)
        basehp = mon.m_lev
        mon.max_hp = mon.hp = 4 * basehp + rng.d(basehp, 4)
    elif not mon.m_lev:
        basehp = 1                     # minimum is 1, raised to 2 below
        mon.max_hp = mon.hp = rng.rnd(4)
    else:
        basehp = mon.m_lev             # at least one per level
        mon.max_hp = mon.hp = rng.d(basehp, 8)
        if is_home_elemental(ptr):
            mon.max_hp = mon.hp = mon.hp * 3

    # if d(X,8) rolled a 1 all X times, give a boost (most useful for
    # level 0 and 1 monsters, and it is what makes the floor 2)
    if mon.max_hp == basehp:
        mon.max_hp += 1
        mon.hp = mon.max_hp


def mbirth_limit(mndx: int) -> int:
    """The population cap for a species (C: makemon.c#mbirth_limit).

    C notes the four-slot limit for "high priest of <deity>" is implicit
    but left at the default, because an aligned priest can grow into one.
    """
    return 9 if mndx == PM_NAZGUL else 3 if mndx == PM_ERINYS else MAXMONNO


# ------------------------------------------------------------
# Mood: peace_minded / set_malign
# ------------------------------------------------------------

def peace_minded(world: World, ptr: PerMonst, rng) -> bool:
    """Is this monster created peaceful?  (C: makemon.c#peace_minded.)

    C's order: the always-peaceful / always-hostile flags, the quest
    leader / nemesis sounds, the Erinys special case, the race tests,
    the alignment comparison, the minion test, and finally a chance roll
    for a co-aligned monster.  Divergences (PLAN-MAKEMON.md §6): there
    is no hero race (race_peaceful / race_hostile are 0), no Amulet, no
    alignment record, and `world.hero_align` is the constant A_NEUTRAL.
    """
    mal = ptr.maligntyp
    ual = world.hero_align

    if always_peaceful(ptr):
        return True
    if always_hostile(ptr):
        return False
    if ptr.msound in (MS_LEADER, MS_GUARDIAN):
        return True
    if ptr.msound == MS_NEMESIS:
        return False
    if ptr.pmidx == PM_ERINYS:
        return True                    # C: !u.ualign.abuse (no record)

    # race_peaceful() / race_hostile(): the hero's race is not ported
    # (always the "human" default), so both are False.

    # hostile if the monster's alignment differs from the hero's
    if sgn(mal) != sgn(ual):
        return False

    # C: `mal < A_NEUTRAL && u.uhave.amulet` -- no Amulet tracking yet

    # minions are hostile to heroes that have strayed at all
    if is_minion(ptr):
        return True                    # C: u.ualign.record >= 0

    # last case: a chance of a co-aligned monster being hostile, greater
    # if the hero has strayed (no record here) and if the monster is not
    # strongly aligned
    return bool(rng.rn2(16)) and bool(rng.rn2(2 + abs(mal)))


def set_malign(world: World, mon: Monster) -> None:
    """Set the monster's alignment score (C: makemon.c#set_malign).

    Negative means "bad to kill" (a peaceful or always-peaceful
    monster), positive means "good to kill".  There is no alignment
    system to spend the score on yet (no alignment record, no
    ualign.hitinc), so this records the C value and nothing acts on it;
    the priest / minion halves wait for their mextra structures.
    """
    ptr = mon.mdata
    assert ptr is not None
    mal = ptr.maligntyp

    coaligned = sgn(mal) == sgn(world.hero_align)
    if ptr.msound == MS_LEADER:
        mon.malign = -20
    elif mal == A_NONE:
        mon.malign = 0 if mon.mpeaceful else 20
    elif always_peaceful(ptr):
        absmal = abs(mal)
        mon.malign = -3 * max(5, absmal) if mon.mpeaceful \
            else 3 * max(5, absmal)         # renegade
    elif always_hostile(ptr):
        mon.malign = 0 if coaligned else max(5, abs(mal))
    elif coaligned:
        absmal = abs(mal)
        mon.malign = -3 * max(3, absmal) if mon.mpeaceful \
            else max(3, absmal)             # renegade
    else:
        mon.malign = abs(mal)               # not coaligned, therefore hostile


# ------------------------------------------------------------
# Where: a random legal square (C: makemon_rnd_goodpos)
# ------------------------------------------------------------

def rnd_goodpos(world: World, rng, map_: Map, lev: int,
                mdat: Optional[PerMonst],
                gpflags: int = 0) -> Optional[Pos]:
    """A random good square (C: makemon.c#makemon_rnd_goodpos).

    50 random tries, then -- if the level is too full for luck -- one
    pass over the whole map in C's rotated order (`(dx + xofs) %
    (COLNO - 1) + 1`), which is what keeps a small or crowded level from
    failing to place anything.  Returns None only when the map has no
    legal square at all (C's "mass drowning on the medusa level" case,
    here a level that is all water for a land monster).

    C's two-pass form (first pass skipping the hero's line of sight,
    second pass dropping GP_CHECKSCARY) becomes one pass: there are no
    appear messages, so "out of the hero's sight" means nothing yet
    (PLAN-MAKEMON.md divergence 6).
    """
    gpflags |= GP_AVOID_MONPOS
    tryct = 0
    nx = ny = 0
    while True:
        nx = rng.rn1(map_.width - 2, 2)      # C: rn1(COLNO - 3, 2)
        ny = rng.rn2(map_.height)            # C: rn2(ROWNO)
        if goodpos(world, rng, map_, lev, (nx, ny), mdat, gpflags):
            return (nx, ny)
        tryct += 1
        if tryct >= 50:
            break

    # C: "else go through all map positions ... first round ignoring
    # positions in sight, and pick first good one"
    xofs, yofs = nx, ny
    for dx in range(map_.width):
        for dy in range(map_.height):
            px = ((dx + xofs) % (map_.width - 1)) + 1
            py = ((dy + yofs) % (map_.height - 1)) + 1
            if goodpos(world, rng, map_, lev, (px, py), mdat, gpflags):
                return (px, py)
    return None


# ------------------------------------------------------------
# With what: the monster's pocket (C: mongets / mkmonmoney)
# ------------------------------------------------------------

def mongets(world: World, rng, mon: Monster, otyp: int) -> Optional[str]:
    """Give a monster one object of type `otyp` (C: makemon.c#mongets).

    The subset of C's body that this port can honour: make the object
    with mksobj() and put it in the monster's inventory through
    core.invent.addinv -- the pack half of the PLAN-INVENT.md
    single-writer rule (a monster's pack carries no letters, so
    addinv's letter half is a hero-only no-op).  C's extra fixups (a
    corpse's corpsenm, the erosion rolls, the "the monster wields it"
    bookkeeping for an AT_WEAP species) ride on mksobj / m_dowear,
    which are phase E work.  Returns the new item's id, or None if
    there is nothing to make.
    """
    from .invent import addinv  # local import: the makemon <- mkobj cycle
    from .mkobj import mksobj  # local import: mkobj imports this module

    if not otyp:
        return None
    item = mksobj(world, rng, otyp)
    addinv(world, mon.id, item)
    return item.id


def mkmonmoney(world: World, rng, mon: Monster, amount: int) -> None:
    """Give a monster a purse of `amount` gold (C: makemon.c#mkmonmoney).

    A gold pile is one object whose `quan` is the amount, so this is
    mkgold() with the monster as the destination instead of the floor.
    """
    from .invent import addinv  # local import: the makemon <- mkobj cycle
    from .mkobj import mksobj, weight  # local import: mkobj imports this

    from .objects import ObjType
    if amount <= 0:
        return
    gold = mksobj(world, rng, ObjType.GOLD_PIECE.value, init=False)
    gold.quan = amount
    gold.owt = weight(world, gold)
    addinv(world, mon.id, gold)


# ------------------------------------------------------------
# makemon -- the funnel
# ------------------------------------------------------------

def makemon(world: World, rng, ptr: Optional[PerMonst] = None,
            pos: Pos = (0, 0), mmflags: MmFlags = NO_MM_FLAGS,
            map_: Optional[Map] = None, lev: Optional[int] = None,
            in_mklev: bool = False) -> Optional[Monster]:
    """Create a monster and put it on the map (C: makemon()).

    `ptr` is the type to create, or None for "whatever is appropriate
    here".  `pos` is where to put it, or (0, 0) for "anywhere legal".
    `map_` / `lev` say which level is being stocked: they default to the
    current one, and the level generator passes the level it is building
    (which may not be the level the hero is standing on).  `in_mklev` is
    C's `gi.in_mklev`, made explicit (PLAN-MAKEMON.md decision 8): it
    changes six things inside the funnel, all of them "this monster is
    part of a new level" rather than "this monster just appeared".

    Returns None for C's NULL: no legal square, a genocided species, or
    an extinct population.  Adding the monster to `world.actors` happens
    before the inventory is filled, exactly where C links it into fmon,
    so a nested call (a group member) sees it.

    `world.hero_or_none` (not `world.hero`) is the hero read: level 1 is
    generated before the hero is placed on the map, and C's `byyou`
    (`u_at(x, y)`) is false then too -- it compares against an unplaced
    (0, 0).
    """
    map_ = world.map if map_ is None else map_
    lev = world.lev if lev is None else lev

    anymon = ptr is None
    hero = world.hero_or_none
    byyou = hero is not None and lev == hero.lev and pos == hero.pos
    allow_minvent = not (mmflags & MmFlags.NO_MINVENT)
    countbirth = not (mmflags & MmFlags.NOCOUNTBIRTH)

    gpflags = GP_CHECKSCARY | GP_AVOID_MONPOS
    if mmflags & MM_IGNOREWATER:
        gpflags |= MM_IGNOREWATER

    x, y = pos

    # --- if the caller wants a random location, do it here ---
    if x == 0 and y == 0:
        got = rnd_goodpos(world, rng, map_, lev, ptr, gpflags)
        if got is None:
            return None
        x, y = got
    elif byyou and not in_mklev:
        # [u.ux,u.uy] means "near the hero"
        near = enexto_core(world, rng, map_, lev, (x, y), ptr, gpflags)
        if near is None:
            near = enexto_core(world, rng, map_, lev, (x, y), ptr,
                               gpflags & ~GP_CHECKSCARY)
        if near is None:
            return None
        x, y = near

    if not map_.in_bounds((x, y)):
        return None                    # C: impossible("bad position")

    # --- does a monster already exist at the position? ---
    if world.monster_at_lev(lev, (x, y)) is not None:
        if not (mmflags & MmFlags.ADJACENTOK):
            return None
        near = enexto_core(world, rng, map_, lev, (x, y), ptr, gpflags)
        if near is None:
            return None
        x, y = near

    if ptr is not None:
        mndx = monsndx(ptr)
        # a specific monster that has already been genocided: no
        if world.mon_state.mvitals[mndx].mvflags & G_GENOD:
            return None
    else:
        # make a random (common) monster that can survive here: the
        # special levels ask for random monsters at specific positions,
        # which is what causes C's "mass drowning" if unchecked
        tryct = 0
        while True:
            nxt = rndmonst(world, rng)
            if nxt is None:
                return None            # no more monsters
            ptr = nxt
            tryct += 1
            if tryct > 50 or goodpos(world, rng, map_, lev, (x, y), ptr,
                                     gpflags):
                break
        mndx = monsndx(ptr)

    world.mon_state.propagate(mndx, countbirth, False, mbirth_limit(mndx))

    mon = Monster(id=world.new_id("mon"), name=monname(ptr), pos=(x, y),
                  hp=0, max_hp=0, ac=ptr.ac, lev=lev,
                  mdata=ptr, mnum=mndx)
    set_mon_data(mon, ptr, 0)
    # C links the monster into fmon here, before the inventory exists
    world.actors[mon.id] = mon

    newmonhp(world, rng, mon, mndx)

    # --- gender ---
    femaleok = not is_male(ptr) and not is_neuter(ptr)
    maleok = not is_female(ptr) and not is_neuter(ptr)
    if is_female(ptr) or ((mmflags & MmFlags.FEMALE) and femaleok):
        mon.female = True
    elif is_male(ptr) or ((mmflags & MmFlags.MALE) and maleok):
        mon.female = False
    else:
        # a neuter monster keeps female = False; the rest roll
        # (C: "female used to be set randomly even for neuters ... but
        # after corpses retain gender it matters")
        mon.female = bool(rng.rn2(2)) if femaleok else False

    if mmflags & MmFlags.ASLEEP:
        mon.sleeping = 1

    mon.mpeaceful = False if (mmflags & MmFlags.ANGRY) \
        else peace_minded(world, ptr, rng)

    # --- per-class fixups (C: the switch on ptr->mlet) ---
    _class_fixups(world, rng, mon, ptr, mndx, lev, x, y, in_mklev)

    set_malign(world, mon)

    # --- groups (C: `if (anymon && !(mmflags & MM_NOGRP))`) --- phase F
    # (m_initsgrp / m_initlgrp); the flag is honoured below by not
    # drawing the group rolls at all.

    if allow_minvent:
        # C: m_initweap (if is_armed), m_initinv, m_dowear -- phase E.
        # The mechanism is mongets()/mkmonmoney(); the species tables
        # are PLAN-MAKEMON.md phase E, so no dice are rolled here and
        # the draw order is stable when they land.
        if is_armed(ptr):
            _initweap(world, rng, mon)
        _initinv(world, rng, mon)
    else:
        # no initial inventory is allowed
        mon.inventory = []

    if ptr.mflags3 and not (mmflags & MmFlags.NOWAIT):
        if ptr.mflags3 & M3_WAITFORU:
            mon.mstrategy |= STRAT_WAITFORU
        if ptr.mflags3 & M3_CLOSE:
            mon.mstrategy |= STRAT_CLOSE
        if ptr.mflags3 & (M3_WAITMASK | M3_COVETOUS):
            mon.mstrategy |= STRAT_APPEARMSG

    # C: the appear message (in_mklev has none, and there is no monster
    # message layer yet -- PLAN-MAKEMON.md divergence 6)
    del anymon, map_
    return mon


def _class_fixups(world: World, rng, mon: Monster, ptr: PerMonst, mndx: int,
                  lev: int, x: int, y: int, in_mklev: bool) -> None:
    """The `switch (ptr->mlet)` block of makemon().

    Kept as its own function so the funnel reads like the C: a mimic's
    disguise (STUB), a spider's or a snake's hidden object, the invisible
    lights, the sleeping leprechaun, the jabberwock / nymph nap, the
    peaceful co-aligned unicorn.
    """
    del mndx
    if ptr.mlet == S_MIMIC:
        pass                       # STUB: set_mimic_sym (display glyphs)
    elif ptr.mlet in (S_SPIDER, S_SNAKE):
        if in_mklev:
            if x and y:
                from .mkobj import mkobj_at  # local import: cycle
                mkobj_at(world, rng, 0, (x, y), lev)   # RANDOM_CLASS = 0
            # C: (void) hideunder(mtmp) -- needs concealment
    elif ptr.mlet in (S_LIGHT, S_ELEMENTAL):
        # C: a stalker / black light is permanently invisible; there is
        # no invisibility in the runtime yet (mhitu docstring)
        pass
    elif ptr.mlet == S_EEL:
        pass                       # C: hideunder() when in_mklev
    elif ptr.mlet == S_LEPRECHAUN:
        mon.sleeping = 1
    elif ptr.mlet in (S_JABBERWOCK, S_NYMPH):
        # C: `if (rn2(5) && !u.uhave.amulet) mtmp->msleeping = 1;`
        if rng.rn2(5):
            mon.sleeping = 1
    elif ptr.mlet == S_ORC:
        # C: `if (Race_if(PM_ELF)) mtmp->mpeaceful = FALSE;` -- the hero
        # has no race yet
        pass
    elif ptr.mlet == S_UNICORN:
        if sgn(world.hero_align) == sgn(ptr.maligntyp):
            mon.mpeaceful = True
    elif ptr.mlet == S_BAT:
        # C: an extra 2 points of speed for a bat in Gehennom
        pass

    if in_mklev:
        # C: a demon / wumpus / long worm / giant eel in a generated
        # level sleeps 4 times in 5 (they lie in wait)
        if _is_ndemon(ptr) and rng.rn2(5):
            mon.sleeping = 1


def _is_ndemon(ptr: PerMonst) -> bool:
    """C: is_ndemon -- a major demon (a demon that is not a lord or a
    prince)."""
    return ptr.mlet == S_DEMON and not (ptr.mflags2 & (M2_LORD | M2_PRINCE))


def _initweap(world: World, rng, mon: Monster) -> None:
    """C: makemon.c#m_initweap (STUB -- PLAN-MAKEMON.md phase E).

    The 413-line C function picks a weapon by species, depth and skill
    and then wields it; the port needs the object tables and m_dowear
    first.  Keeping it a named no-op (rather than folding it into
    makemon) means the draw order does not change when it lands.
    """
    del world, rng, mon


def _initinv(world: World, rng, mon: Monster) -> None:
    """C: makemon.c#m_initinv (STUB -- PLAN-MAKEMON.md phase E).

    The per-class extras: a jelly's treasure, a leprechaun's gold, a
    nymph's items, a soldier's kit.  ``mongets`` / ``mkmonmoney`` are
    the mechanism, so the fill-in is a table plus calls to those.
    """
    del world, rng, mon


__all__ = [
    "MAXMONNO", "MongenOrder",
    "STRAT_APPEARMSG", "STRAT_CLOSE", "STRAT_NONE", "STRAT_WAITFORU",
    "STRAT_WAITMASK",
    "adj_lev", "align_shift", "golemhp", "gen_ok", "is_home_elemental",
    "makemon", "mbirth_limit", "mkclass", "mkclass_aligned", "mkmonmoney",
    "monhp_per_lvl", "mongen_order", "mongets", "monmax_difficulty",
    "monmin_difficulty", "newmonhp", "peace_minded", "rnd_goodpos",
    "rndmonst", "rndmonst_adj", "set_malign", "temperature_shift",
    "uncommon",
]
