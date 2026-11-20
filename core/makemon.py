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
  initweap() / initinv() / initthrow()
                                 the species kits (m_initweap /
                                 m_initinv / m_initthrow)
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

  - ``m_dowear()`` (C: do_wear.c): the monster putting its own armour
    on after the kit is handed out.  ``initweap()`` / ``initinv()``
    fill the pack (PLAN-MAKEMON.md phase E) -- a soldier carries the
    sword and the mail -- but nothing wears it yet, so a monster's AC
    is still its ``PerMonst.ac`` (PLAN-ARMOR.md §5 lists the monster
    armour half).
  - ``m_initgrp()`` / ``m_initsgrp()`` / ``m_initlgrp()``: monster
    groups (soldier squads, orc bands) -- phase F.  The generator passes
    MM_NOGRP meanwhile, so the flag is honoured, not faked.
  - ``set_mimic_sym()``: a mimic needs the display glyph machinery, and
    ``hideunder()`` (a spider / eel under a wall) needs concealment.
  - ``grow_up()`` / ``clone_mon()`` / ``create_critters()`` /
    ``unmakemon()``: phase F.
  - ``christen_monst()`` and the "A kobold appears!" message: there is
    no monster message layer yet, so MM_NOMSG is effectively always on.
  - the ``mtmp->cham`` (shapechanger) and ``iswiz`` halves: no
    polymorph, no quest.
  - the ``mextra`` half: ``MM_EPRI`` allocates the priest extra
    (``Monster.epri``, the C newepri) and core.priest.priestini fills
    it (PLAN-SPECIAL-ROOMS.md phase 1); ``MM_ESHK`` allocates the
    shopkeeper extra (``Monster.eshk``, the C neweshk) and
    core.shk.init fills it (phase 4a).  MM_EDOG / MM_EMIN / MM_EGD are
    still accepted and ignored (their systems land with the pet /
    minion work).  C's "a cleric made without MM_EPRI gets an emin
    instead" tail (the roaming-priest half) is not ported: pyhack has
    no emin.

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
from .mondata import (
    always_hostile,
    always_peaceful,
    extra_nasty,
    genus,
    humanoid,
    is_armed,
    is_demon,
    is_dwarf,
    is_elf,
    is_female,
    is_giant,
    is_lord,
    is_male,
    is_mercenary,
    is_minion,
    is_neuter,
    is_placeholder,
    is_prince,
    is_rider,
    likes_gold,
    set_mon_data,
    strongmonst,
)
from .monst import (
    A_NONE,
    G_FREQ,
    G_GENOD,
    G_GONE,
    G_HELL,
    G_NOGEN,
    G_UNIQ,
    LOW_PM,
    M2_LORD,
    M2_PRINCE,
    M3_CLOSE,
    M3_COVETOUS,
    M3_WAITFORU,
    M3_WAITMASK,
    MAXMCLASSES,
    MONS,
    MS_GUARDIAN,
    MS_LEADER,
    MS_NEMESIS,
    MS_PRIEST,
    PM_ELVEN_MONARCH,
    PM_ERINYS,
    PM_GRAY_DRAGON,
    PM_IRON_GOLEM,
    PM_MORDOR_ORC,
    PM_NAMES,
    PM_NAZGUL,
    PM_ORC_CAPTAIN,
    PM_ORC_SHAMAN,
    PM_STONE_GOLEM,
    PM_URUK_HAI,
    PM_WIZARD_OF_YENDOR,
    S_ANGEL,
    S_BAT,
    S_CENTAUR,
    S_DEMON,
    S_EEL,
    S_ELEMENTAL,
    S_GIANT,
    S_GNOME,
    S_HUMAN,
    S_HUMANOID,
    S_JABBERWOCK,
    S_KOBOLD,
    S_KOP,
    S_LEPRECHAUN,
    S_LICH,
    S_LIGHT,
    S_LIZARD,
    S_MIMIC,
    S_MUMMY,
    S_NYMPH,
    S_OGRE,
    S_ORC,
    S_QUANTMECH,
    S_SNAKE,
    S_SPIDER,
    S_TROLL,
    S_UNICORN,
    S_WRAITH,
    S_ZOMBIE,
    SPECIAL_PM,
    PerMonst,
    is_golem,
    monname,
    monsndx,
)
from .objects import OBJECTS, ObjClass, ObjType, Skill
from .place import enexto_core, goodpos
from .types import (
    Epri,
    Eshk,
    GP_AVOID_MONPOS,
    GP_CHECKSCARY,
    Item,
    MM_IGNOREWATER,
    Map,
    MmFlags,
    Monster,
    NO_MM_FLAGS,
    Pos,
    World,
)

O = ObjType  # noqa: E741 -- the house alias for the object table

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


def _pm(name: str) -> int:
    """The ``mons[]`` index of a species by its neutral name (C: the
    PM_ constant spelled out).  ``PM_NAMES`` is the complete C ordering,
    so this resolves the species the PM_ anchors core.monst re-exports
    do not cover."""
    return PM_NAMES.index(name)


#: C: the quest guardians whose kit m_initweap's MS_GUARDIAN branch
#: groups together: the scholars (a dagger, light armour, boots, a
#: healing potion) and the fighters (a sword, mail, boots, a cloak).
#: Resolved at import time, so a mistyped species name fails the import
#: instead of a mid-level makemon.
_SCHOLAR_GUARDIANS = frozenset(
    _pm(n) for n in ("student", "attendant", "abbot", "acolyte", "guide", "apprentice")
)
_FIGHTER_GUARDIANS = frozenset(
    _pm(n) for n in ("chieftain", "page", "roshi", "warrior")
)

#: every other species the starting kits name, resolved (and therefore
#: validated) at import time -- see _SCHOLAR_GUARDIANS.
_KIT_SPECIES = tuple(
    _pm(n)
    for n in (
        "ettin",
        "watchman",
        "soldier",
        "sergeant",
        "lieutenant",
        "captain",
        "watch captain",
        "guard",
        "shopkeeper",
        "ninja",
        "cleric",
        "monk",
        "hobbit",
        "salamander",
        "balrog",
        "Orcus",
        "horned devil",
        "Dispater",
        "Yeenoghu",
        "ice devil",
        "Asmodeus",
        "housecat",
        "quantum mechanic",
        "master lich",
        "arch-lich",
        "minotaur",
        "ogre tyrant",
        "ogre leader",
        "forest centaur",
        "hunter",
        "thug",
        "neanderthal",
    )
)


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


def rndmonst_adj(world: World, rng, minadj: int, maxadj: int) -> Optional[PerMonst]:
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
            continue  # a row the port lacks yet
        if ptr.difficulty < minmlev or ptr.difficulty > maxmlev:
            continue
        if uncommon(world, mndx):
            continue
        weight = (ptr.geno & G_FREQ) + align_shift(ptr) + temperature_shift(world, ptr)
        if weight < 0 or weight > 127:
            weight = 0  # C: impossible("bad weight")
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
        order: List[int] = [i for i in range(LOW_PM, SPECIAL_PM) if MONS[i] is not None]
        maxf = [0] * MAXMCLASSES
        for mndx in order:
            ptr = MONS[mndx]
            assert ptr is not None  # narrowed by the comprehension
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


def gen_ok(world: World, mndx: int, mvflagsmask: int, genomask: int) -> bool:
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


def mkclass(world: World, rng, mclass: int, spc: int = 0) -> Optional[PerMonst]:
    """A random species of monster class `mclass` (C: mkclass), or None.

    `spc` is C's "special mons[].geno handling": the geno bits to ignore
    (G_NOGEN | G_UNIQ by default), plus G_IGNORE to also accept the
    genocided / extinct species.
    """
    return mkclass_aligned(world, rng, mclass, spc, A_NONE)


def mkclass_aligned(
    world: World, rng, mclass: int, spc: int, atyp: int
) -> Optional[PerMonst]:
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
        return None  # C: impossible("bad class")
    zero_freq_for_entire_class = mo.maxf[mclass] == 0

    order = mo.order
    first = 0
    while first < len(order):
        row = MONS[order[first]]
        assert row is not None  # order holds implemented rows
        if row.mlet == mclass:
            break
        first += 1
    if first == len(order):
        return None  # C: no such class implemented

    mv_mask: int = int(G_GONE)
    if spc & 0x8000:  # C: G_IGNORE
        mv_mask = 0
        spc &= ~0x8000

    nums: Dict[int, int] = {}
    num = 0
    last = first
    while last < len(order):
        mndx = order[last]
        ptr = MONS[mndx]
        assert ptr is not None  # order holds implemented rows
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


def ndemon(world: World, rng, atyp: int) -> Optional[int]:
    """A random major demon, as a mons[] index (C: minion.c#ndemon),
    or None (C: NON_PM).  `atyp` is the alignment restriction; A_NONE
    means any alignment.

    C's one-try contract, kept: mkclass_aligned() picks the species in
    one draw and is_ndemon() rejects the lords and princes -- a failed
    pick answers None, it does not retry (the C comment: the old 20-try
    loop is gone).
    """
    ptr = mkclass_aligned(world, rng, S_DEMON, 0, atyp)
    if ptr is not None and _is_ndemon(ptr):
        return monsndx(ptr)
    return None


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
        return 50  # "special" demons / devils
    tmp = ptr.mlevel
    tmp2 = rules.level_difficulty(world) - tmp
    if tmp2 < 0:
        tmp -= 1  # weaker than the level: drop one
    else:
        tmp += tmp2 // 5  # one per five of difference
    tmp2 = world.hero_ulevel - ptr.mlevel
    if tmp2 > 0:
        tmp += tmp2 // 4  # and one per four of hero level
    tmp2 = (3 * ptr.mlevel) // 2  # crude upper limit
    if tmp2 > 49:
        tmp2 = 49
    if tmp > tmp2:
        tmp = tmp2
    return tmp if tmp > 0 else 0


def golemhp(mndx: int) -> int:
    """A golem's fixed hit points (C: makemon.c#golemhp)."""
    table = {
        249: 20,  # C: PM_STRAW_GOLEM
        250: 20,  # C: PM_PAPER_GOLEM
        251: 30,  # C: PM_ROPE_GOLEM
        252: 60,  # C: PM_GOLD_GOLEM
        253: 40,  # C: PM_LEATHER_GOLEM
        254: 50,  # C: PM_WOOD_GOLEM
        255: 40,  # C: PM_FLESH_GOLEM
        256: 70,  # C: PM_CLAY_GOLEM
        PM_STONE_GOLEM: 100,
        258: 80,  # C: PM_GLASS_GOLEM
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
    hp = rng.rnd(8)  # default is d8
    if is_golem(ptr):
        mlev = ptr.mlevel or 1
        hp = golemhp(monsndx(ptr)) // mlev
    elif ptr.mlevel > 49:
        hp = 4 + rng.rnd(4)  # 5..8, arbitrary
    elif ptr.mlet == 30 and monsndx(ptr) >= PM_GRAY_DRAGON:
        # C: S_DRAGON; adult dragons roll 4..8 here
        hp = 4 + rng.rn2(5)
    elif not mon.m_lev:
        hp = rng.rnd(4)  # level 0 monsters use 1d4
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
        mon.m_lev = mon.hp // 4  # approximation
    elif ptr.mlet == 30 and mndx >= PM_GRAY_DRAGON:
        # C: S_DRAGON; adult dragons roll N*(4+d4) (N*8 in the endgame,
        # which is not modelled)
        basehp = mon.m_lev
        mon.max_hp = mon.hp = 4 * basehp + rng.d(basehp, 4)
    elif not mon.m_lev:
        basehp = 1  # minimum is 1, raised to 2 below
        mon.max_hp = mon.hp = rng.rnd(4)
    else:
        basehp = mon.m_lev  # at least one per level
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
        return True  # C: !u.ualign.abuse (no record)

    # race_peaceful() / race_hostile(): the hero's race is not ported
    # (always the "human" default), so both are False.

    # hostile if the monster's alignment differs from the hero's
    if sgn(mal) != sgn(ual):
        return False

    # C: `mal < A_NEUTRAL && u.uhave.amulet` -- no Amulet tracking yet

    # minions are hostile to heroes that have strayed at all
    if is_minion(ptr):
        return True  # C: u.ualign.record >= 0

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
        mon.malign = (
            -3 * max(5, absmal) if mon.mpeaceful else 3 * max(5, absmal)
        )  # renegade
    elif always_hostile(ptr):
        mon.malign = 0 if coaligned else max(5, abs(mal))
    elif coaligned:
        absmal = abs(mal)
        mon.malign = (
            -3 * max(3, absmal) if mon.mpeaceful else max(3, absmal)
        )  # renegade
    else:
        mon.malign = abs(mal)  # not coaligned, therefore hostile


# ------------------------------------------------------------
# Where: a random legal square (C: makemon_rnd_goodpos)
# ------------------------------------------------------------


def rnd_goodpos(
    world: World, rng, map_: Map, lev: int, mdat: Optional[PerMonst], gpflags: int = 0
) -> Optional[Pos]:
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
        nx = rng.rn1(map_.width - 2, 2)  # C: rn1(COLNO - 3, 2)
        ny = rng.rn2(map_.height)  # C: rn2(ROWNO)
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
    which are phase E work.  Returns the id of the stack the object
    ended up in, or None if there is nothing to make.

    That is the *survivor*'s id, not the new object's: a monster's pack
    merges (C: addinv -> mpickobj -> add_to_minv -> merged), so a second
    dagger joins the one already there and the freshly made object is
    deleted.  C's mongets answers the object it built, which after a
    merge is a dangling pointer -- this port answers the stack that
    holds it, which is what m_initinv's `otmp = mongets(...)` idiom
    (mongets_item below) has to read.
    """
    from .invent import addinv  # local import: the makemon <- mkobj cycle
    from .mkobj import mksobj  # local import: mkobj imports this module

    if not otyp:
        return None
    item = mksobj(world, rng, otyp)
    return addinv(world, mon.id, item).id


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


def makemon(
    world: World,
    rng,
    ptr: Optional[PerMonst] = None,
    pos: Pos = (0, 0),
    mmflags: MmFlags = NO_MM_FLAGS,
    map_: Optional[Map] = None,
    lev: Optional[int] = None,
    in_mklev: bool = False,
) -> Optional[Monster]:
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
            near = enexto_core(
                world, rng, map_, lev, (x, y), ptr, gpflags & ~GP_CHECKSCARY
            )
        if near is None:
            return None
        x, y = near

    if not map_.in_bounds((x, y)):
        return None  # C: impossible("bad position")

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
                return None  # no more monsters
            ptr = nxt
            tryct += 1
            if tryct > 50 or goodpos(world, rng, map_, lev, (x, y), ptr, gpflags):
                break
        mndx = monsndx(ptr)

    world.mon_state.propagate(mndx, countbirth, False, mbirth_limit(mndx))

    mon = Monster(
        id=world.new_id("mon"),
        name=monname(ptr),
        pos=(x, y),
        hp=0,
        max_hp=0,
        ac=ptr.ac,
        lev=lev,
        mdata=ptr,
        mnum=mndx,
    )
    set_mon_data(mon, ptr, 0)
    # C links the monster into fmon here, before the inventory exists
    world.actors[mon.id] = mon
    # C: the mextra allocation half of the MM_* flags (the newepri /
    # neweshk block, makemon.c): MM_EPRI allocates the priest extra
    # here and priestini() fills it afterwards (PLAN-SPECIAL-ROOMS.md
    # phase 1); MM_ESHK allocates the shopkeeper extra and
    # core.shk.init() fills it (phase 4a); the other extras wait for
    # their systems (module docstring)
    if mmflags & MmFlags.EPRI:
        mon.epri = Epri()
    if mmflags & MmFlags.ESHK:
        # C: neweshk() -- a zeroed struct with the owner recorded
        mon.eshk = Eshk(parentmid=mon.id)

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

    mon.mpeaceful = (
        False if (mmflags & MmFlags.ANGRY) else peace_minded(world, ptr, rng)
    )

    # --- per-class fixups (C: the switch on ptr->mlet) ---
    _class_fixups(world, rng, mon, ptr, mndx, lev, x, y, in_mklev)

    set_malign(world, mon)

    # --- groups (C: `if (anymon && !(mmflags & MM_NOGRP))`) --- phase F
    # (m_initsgrp / m_initlgrp); the flag is honoured below by not
    # drawing the group rolls at all.

    if allow_minvent:
        # C: m_initweap (if is_armed), m_initinv, m_dowear.  m_dowear
        # -- the monster putting its own armour on -- is the armouring
        # half of monsters, not ported (PLAN-ARMOR.md §5 names it); the
        # kit itself is real, so a soldier carries its sword.
        if is_armed(ptr):
            initweap(world, rng, mon)
        initinv(world, rng, mon)
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


def _class_fixups(
    world: World,
    rng,
    mon: Monster,
    ptr: PerMonst,
    mndx: int,
    lev: int,
    x: int,
    y: int,
    in_mklev: bool,
) -> None:
    """The `switch (ptr->mlet)` block of makemon().

    Kept as its own function so the funnel reads like the C: a mimic's
    disguise (STUB), a spider's or a snake's hidden object, the invisible
    lights, the sleeping leprechaun, the jabberwock / nymph nap, the
    peaceful co-aligned unicorn.
    """
    del mndx
    if ptr.mlet == S_MIMIC:
        pass  # STUB: set_mimic_sym (display glyphs)
    elif ptr.mlet in (S_SPIDER, S_SNAKE):
        if in_mklev:
            if x and y:
                from .mkobj import mkobj_at  # local import: cycle

                mkobj_at(world, rng, 0, (x, y), lev)  # RANDOM_CLASS = 0
            # C: (void) hideunder(mtmp) -- needs concealment
    elif ptr.mlet in (S_LIGHT, S_ELEMENTAL):
        # C: a stalker / black light is permanently invisible; there is
        # no invisibility in the runtime yet (mhitu docstring)
        pass
    elif ptr.mlet == S_EEL:
        pass  # C: hideunder() when in_mklev
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


def initweap(world: World, rng, mon: Monster) -> None:
    """Equip an armed monster with weapons, armour and thrown ammo (C:
    makemon.c#m_initweap, 160-572).

    C's 413 lines are one ``switch (ptr->mlet)``: a handful of species
    get a bespoke kit (a giant's boulder, a soldier's polearm, an elf's
    elven gear, an orc's scimitar) and everything else falls through to
    the *general case* -- ``rnd(14 - 2*bias)`` against a six-row table
    of weapons, ``bias`` being ``is_lord + 2*is_prince +
    extra_nasty``.  This is that switch, with C's draw order kept draw
    for draw (including the ``do { } while`` that re-rolls the soldier's
    polearm until it is really a polearm, and the short-circuited
    ``rn2()`` calls).

    Skipped, each for a system that does not exist here (the branches
    are named so nobody re-decides them):

    - ``Is_rogue_level()``'s early return (no rogue level);
    - the angel's ``oname()`` artifact promotion -- the ``rn2(20)`` roll
      is still taken so the sequence stays put (no artifacts);
    - ``gi.in_mklev && Is_earthlevel()`` in the elven-monarch and
      minotaur branches (no Gehennom);
    - the poison on an orcish arrow (``Item`` has no ``opoisoned``);
    - C's tail ``mongets(rnd_offensive_item(mtmp))`` -- that is muse.c's
      table, not this file's; the ``rn2(75)`` gate is still rolled.
    """
    from .invent import addinv  # local import: the makemon <- mkobj cycle
    from .mkobj import bless, curse, mksobj  # local import: cycle

    ptr = mon.mdata
    assert ptr is not None  # makemon always sets it
    mm = ptr.pmidx

    if ptr.mlet == S_GIANT:
        # a giant's boulder (an ettin's club) and sometimes a big weapon
        if rng.rn2(2):
            mongets(
                world, rng, mon, int(O.CLUB) if mm == _pm("ettin") else int(O.BOULDER)
            )
        if mm != _pm("ettin") and not rng.rn2(5):
            mongets(
                world,
                rng,
                mon,
                int(O.TWO_HANDED_SWORD) if rng.rn2(2) else int(O.BATTLE_AXE),
            )
    elif ptr.mlet == S_HUMAN:
        if is_mercenary(ptr):
            w1 = w2 = 0
            if mm in (_pm("watchman"), _pm("soldier")):
                if not rng.rn2(3):
                    # a random polearm -- the rn1 range holds the lance
                    # and the dwarvish mattock, which use other skills
                    while True:
                        w1 = rng.rn1(
                            int(O.BEC_DE_CORBIN) - int(O.PARTISAN) + 1,
                            int(O.PARTISAN),
                        )
                        if OBJECTS[w1].subtyp == Skill.P_POLEARMS:
                            break
                    w2 = int(O.DAGGER) if rng.rn2(2) else int(O.KNIFE)
                else:
                    w1 = int(O.SPEAR) if rng.rn2(2) else int(O.SHORT_SWORD)
            elif mm == _pm("sergeant"):
                w1 = int(O.FLAIL) if rng.rn2(2) else int(O.MACE)
            elif mm == _pm("lieutenant"):
                w1 = int(O.BROADSWORD) if rng.rn2(2) else int(O.LONG_SWORD)
            elif mm in (_pm("captain"), _pm("watch captain")):
                w1 = int(O.LONG_SWORD) if rng.rn2(2) else int(O.SILVER_SABER)
            else:
                if not rng.rn2(4):
                    w1 = int(O.DAGGER)
                if not rng.rn2(7):
                    w2 = int(O.SPEAR)
            if w1:
                mongets(world, rng, mon, w1)
            if not w2 and w1 != int(O.DAGGER) and not rng.rn2(4):
                w2 = int(O.KNIFE)
            if w2:
                mongets(world, rng, mon, w2)
        elif is_elf(ptr):
            if rng.rn2(2):
                mongets(
                    world,
                    rng,
                    mon,
                    int(O.ELVEN_MITHRIL_COAT) if rng.rn2(2) else int(O.ELVEN_CLOAK),
                )
            if rng.rn2(2):
                mongets(world, rng, mon, int(O.ELVEN_LEATHER_HELM))
            elif not rng.rn2(4):
                mongets(world, rng, mon, int(O.ELVEN_BOOTS))
            if rng.rn2(2):
                mongets(world, rng, mon, int(O.ELVEN_DAGGER))
            kit = rng.rn2(3)
            if kit == 0:
                if not rng.rn2(4):
                    mongets(world, rng, mon, int(O.ELVEN_SHIELD))
                if rng.rn2(3):
                    mongets(world, rng, mon, int(O.ELVEN_SHORT_SWORD))
                mongets(world, rng, mon, int(O.ELVEN_BOW))
                initthrow(world, rng, mon, int(O.ELVEN_ARROW), 12)
            elif kit == 1:
                mongets(world, rng, mon, int(O.ELVEN_BROADSWORD))
                if rng.rn2(2):
                    mongets(world, rng, mon, int(O.ELVEN_SHIELD))
            else:
                if rng.rn2(2):
                    mongets(world, rng, mon, int(O.ELVEN_SPEAR))
                    mongets(world, rng, mon, int(O.ELVEN_SHIELD))
            if mm == PM_ELVEN_MONARCH:
                if rng.rn2(3):
                    mongets(world, rng, mon, int(O.PICK_AXE))
                if not rng.rn2(50):
                    mongets(world, rng, mon, int(O.CRYSTAL_BALL))
        elif ptr.msound == MS_PRIEST or _quest_role(ptr) == _pm("cleric"):
            # C: mace of random enchantment, half of them cursed
            mace = mksobj(world, rng, int(O.MACE), False, False)
            mace.spe = rng.rnd(3)
            if not rng.rn2(2):
                curse(mace)
            addinv(world, mon.id, mace)
        elif mm == _pm("ninja"):
            mongets(
                world,
                rng,
                mon,
                int(O.SHURIKEN) if rng.rn2(4) else int(O.DART),
            )
            mongets(
                world,
                rng,
                mon,
                int(O.SHORT_SWORD) if rng.rn2(4) else int(O.AXE),
            )
        elif ptr.msound == MS_GUARDIAN:
            _quest_guardian_kit(world, rng, mon, mm)
    elif ptr.mlet == S_ANGEL:
        if humanoid(ptr):
            # C: "create minion stuff; bypass mongets"
            typ = int(O.LONG_SWORD) if rng.rn2(3) else int(O.SILVER_MACE)
            weapon = mksobj(world, rng, typ, False, False)
            # C: `(!rn2(20) || is_lord(ptr)) && sgn(maligntyp) ==
            # A_LAWFUL` -> oname(otmp, "Sunsword"/"Demonbane"); no
            # artifacts here, but the roll stays in the sequence
            rng.rn2(20)
            bless(weapon)
            weapon.oerodeproof = True
            weapon.spe = rng.rn2(4)
            if typ == int(O.SILVER_MACE):
                weapon.spe += 3
            addinv(world, mon.id, weapon)
            shield = mksobj(
                world,
                rng,
                int(O.SHIELD_OF_REFLECTION) if not rng.rn2(4) else int(O.LARGE_SHIELD),
                False,
                False,
            )
            shield.oerodeproof = True
            shield.spe = 0
            addinv(world, mon.id, shield)
    elif ptr.mlet == S_HUMANOID:
        if mm == _pm("hobbit"):
            kit = rng.rn2(3)
            if kit == 0:
                mongets(world, rng, mon, int(O.DAGGER))
            elif kit == 1:
                mongets(world, rng, mon, int(O.ELVEN_DAGGER))
            else:
                mongets(world, rng, mon, int(O.SLING))
                initthrow(
                    world,
                    rng,
                    mon,
                    int(O.FLINT) if not rng.rn2(4) else int(O.ROCK),
                    6,
                )
            if not rng.rn2(10):
                mongets(world, rng, mon, int(O.ELVEN_MITHRIL_COAT))
            if not rng.rn2(10):
                mongets(world, rng, mon, int(O.DWARVISH_CLOAK))
        elif is_dwarf(ptr):
            if rng.rn2(7):
                mongets(world, rng, mon, int(O.DWARVISH_CLOAK))
            if rng.rn2(7):
                mongets(world, rng, mon, int(O.IRON_SHOES))
            if not rng.rn2(4):
                mongets(world, rng, mon, int(O.DWARVISH_SHORT_SWORD))
                if rng.rn2(2):
                    mongets(world, rng, mon, int(O.DWARVISH_MATTOCK))
                else:
                    mongets(
                        world,
                        rng,
                        mon,
                        int(O.AXE) if rng.rn2(2) else int(O.DWARVISH_SPEAR),
                    )
                    mongets(world, rng, mon, int(O.DWARVISH_ROUNDSHIELD))
                mongets(world, rng, mon, int(O.DWARVISH_IRON_HELM))
                if not rng.rn2(3):
                    mongets(world, rng, mon, int(O.DWARVISH_MITHRIL_COAT))
            else:
                mongets(
                    world,
                    rng,
                    mon,
                    int(O.PICK_AXE) if not rng.rn2(3) else int(O.DAGGER),
                )
    elif ptr.mlet == S_KOP:
        # C: Keystone Kops with cream pies to throw [MRS]
        if not rng.rn2(4):
            initthrow(world, rng, mon, int(O.CREAM_PIE), 2)
        if not rng.rn2(3):
            mongets(world, rng, mon, int(O.CLUB) if rng.rn2(2) else int(O.RUBBER_HOSE))
    elif ptr.mlet == S_ORC:
        if rng.rn2(2):
            mongets(world, rng, mon, int(O.ORCISH_HELM))
        kind = (
            mm
            if mm != PM_ORC_CAPTAIN
            else (PM_MORDOR_ORC if rng.rn2(2) else PM_URUK_HAI)
        )
        if kind == PM_MORDOR_ORC:
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.SCIMITAR))
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.ORCISH_SHIELD))
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.KNIFE))
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.ORCISH_CHAIN_MAIL))
        elif kind == PM_URUK_HAI:
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.ORCISH_CLOAK))
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.ORCISH_SHORT_SWORD))
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.IRON_SHOES))
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.ORCISH_BOW))
                initthrow(world, rng, mon, int(O.ORCISH_ARROW), 12)
            if not rng.rn2(3):
                mongets(world, rng, mon, int(O.URUK_HAI_SHIELD))
        else:
            if mm != PM_ORC_SHAMAN and rng.rn2(2):
                mongets(
                    world,
                    rng,
                    mon,
                    (
                        int(O.ORCISH_DAGGER)
                        if mm == _pm("goblin") or rng.rn2(2) == 0
                        else int(O.SCIMITAR)
                    ),
                )
    elif ptr.mlet == S_OGRE:
        # a tyrant is likelier to have the axe than a plain ogre
        chance = (
            3 if mm == _pm("ogre tyrant") else 6 if mm == _pm("ogre leader") else 12
        )
        if not rng.rn2(chance):
            mongets(world, rng, mon, int(O.BATTLE_AXE))
        else:
            mongets(world, rng, mon, int(O.CLUB))
    elif ptr.mlet == S_TROLL:
        if not rng.rn2(2):
            polearm = rng.rn2(4)
            mongets(
                world,
                rng,
                mon,
                (
                    int(O.RANSEUR),
                    int(O.PARTISAN),
                    int(O.GLAIVE),
                    int(O.SPETUM),
                )[polearm],
            )
    elif ptr.mlet == S_KOBOLD:
        if not rng.rn2(4):
            initthrow(world, rng, mon, int(O.DART), 12)
    elif ptr.mlet == S_CENTAUR:
        if rng.rn2(2):
            if ptr.pmnames[2] == "forest centaur":
                mongets(world, rng, mon, int(O.BOW))
                initthrow(world, rng, mon, int(O.ARROW), 12)
            else:
                mongets(world, rng, mon, int(O.CROSSBOW))
                initthrow(world, rng, mon, int(O.CROSSBOW_BOLT), 12)
    elif ptr.mlet == S_WRAITH:
        mongets(world, rng, mon, int(O.KNIFE))
        mongets(world, rng, mon, int(O.LONG_SWORD))
    elif ptr.mlet == S_ZOMBIE:
        if not rng.rn2(4):
            mongets(world, rng, mon, int(O.LEATHER_ARMOR))
        if not rng.rn2(4):
            mongets(world, rng, mon, int(O.KNIFE) if rng.rn2(3) else int(O.SHORT_SWORD))
    elif ptr.mlet == S_LIZARD:
        if mm == _pm("salamander"):
            mongets(
                world,
                rng,
                mon,
                (
                    int(O.SPEAR)
                    if rng.rn2(7)
                    else (int(O.TRIDENT) if rng.rn2(3) else int(O.STILETTO))
                ),
            )
    elif ptr.mlet == S_DEMON:
        if mm == _pm("balrog"):
            mongets(world, rng, mon, int(O.BULLWHIP))
            mongets(world, rng, mon, int(O.BROADSWORD))
        elif mm == _pm("Orcus"):
            mongets(world, rng, mon, int(O.WAN_DEATH))  # the Wand of Orcus
        elif mm == _pm("horned devil"):
            mongets(world, rng, mon, int(O.TRIDENT) if rng.rn2(4) else int(O.BULLWHIP))
        elif mm == _pm("Dispater"):
            mongets(world, rng, mon, int(O.WAN_STRIKING))
        elif mm == _pm("Yeenoghu"):
            mongets(world, rng, mon, int(O.FLAIL))
        # C: "prevent djinn and mail daemons from leaving objects when
        # they vanish" -- a real demon falls through to the general case
        if is_demon(ptr):
            _general_weapon(world, rng, mon, ptr)
    else:
        _general_weapon(world, rng, mon, ptr)

    # C: `if ((int) mtmp->m_lev > rn2(75)) mongets(rnd_offensive_item)`.
    # The roll is taken (the draw-order rule); the item is muse.c's.
    mon.m_lev > rng.rn2(75)


def _general_weapon(world: World, rng, mon: Monster, ptr: PerMonst) -> None:
    """C: m_initweap's ``default:`` case -- "some chance of getting
    some type of weapon for normal monsters": ``rnd(14 - 2*bias)``
    against the six-row table, with strong monsters getting the heavy
    version of each row and weak ones the thrown version.
    """
    bias = (1 if is_lord(ptr) else 0) + 2 * (1 if is_prince(ptr) else 0)
    bias += 1 if extra_nasty(ptr) else 0
    roll = rng.rnd(14 - 2 * bias)
    strong = strongmonst(ptr)
    if roll == 1:
        if strong:
            mongets(world, rng, mon, int(O.BATTLE_AXE))
        else:
            initthrow(world, rng, mon, int(O.DART), 12)
    elif roll == 2:
        if strong:
            mongets(world, rng, mon, int(O.TWO_HANDED_SWORD))
        else:
            mongets(world, rng, mon, int(O.CROSSBOW))
            initthrow(world, rng, mon, int(O.CROSSBOW_BOLT), 12)
    elif roll == 3:
        mongets(world, rng, mon, int(O.BOW))
        initthrow(world, rng, mon, int(O.ARROW), 12)
    elif roll == 4:
        if strong:
            mongets(world, rng, mon, int(O.LONG_SWORD))
        else:
            initthrow(world, rng, mon, int(O.DAGGER), 3)
    elif roll == 5:
        if strong:
            mongets(world, rng, mon, int(O.LUCERN_HAMMER))
        else:
            mongets(world, rng, mon, int(O.AKLYS))


def _quest_guardian_kit(world: World, rng, mon: Monster, mm: int) -> None:
    """C: m_initweap's ``MS_GUARDIAN`` half -- the quest guardians'
    starting kits.  The ``switch`` groups are kept as C has them: the
    three scholarly guardians (a dagger, light armour, boots, a healing
    potion), the four fighters (a sword, mail, boots, a cloak and
    sometimes a bow) and the three one-off kits.
    """
    scholar = _SCHOLAR_GUARDIANS
    fighter = _FIGHTER_GUARDIANS
    if mm in scholar:
        if rng.rn2(2):
            mongets(world, rng, mon, int(O.DAGGER) if rng.rn2(3) else int(O.KNIFE))
        if rng.rn2(5):
            mongets(
                world,
                rng,
                mon,
                int(O.LEATHER_JACKET) if rng.rn2(3) else int(O.LEATHER_CLOAK),
            )
        if rng.rn2(3):
            mongets(
                world, rng, mon, int(O.LOW_BOOTS) if rng.rn2(3) else int(O.HIGH_BOOTS)
            )
        if rng.rn2(3):
            mongets(world, rng, mon, int(O.POT_HEALING))
    elif mm in fighter:
        mongets(
            world, rng, mon, int(O.LONG_SWORD) if rng.rn2(3) else int(O.SHORT_SWORD)
        )
        mongets(
            world, rng, mon, int(O.CHAIN_MAIL) if rng.rn2(3) else int(O.LEATHER_ARMOR)
        )
        if rng.rn2(2):
            mongets(
                world, rng, mon, int(O.LOW_BOOTS) if rng.rn2(2) else int(O.HIGH_BOOTS)
            )
        if not rng.rn2(3):
            mongets(world, rng, mon, int(O.LEATHER_CLOAK))
        if not rng.rn2(3):
            mongets(world, rng, mon, int(O.BOW))
            initthrow(world, rng, mon, int(O.ARROW), 12)
    elif mm == _pm("hunter"):
        mongets(world, rng, mon, int(O.SHORT_SWORD) if rng.rn2(3) else int(O.DAGGER))
        if rng.rn2(2):
            mongets(
                world,
                rng,
                mon,
                int(O.LEATHER_JACKET) if rng.rn2(2) else int(O.LEATHER_ARMOR),
            )
        mongets(world, rng, mon, int(O.BOW))
        initthrow(world, rng, mon, int(O.ARROW), 12)
    elif mm == _pm("thug"):
        mongets(world, rng, mon, int(O.CLUB))
        mongets(world, rng, mon, int(O.DAGGER) if rng.rn2(3) else int(O.KNIFE))
        if rng.rn2(2):
            mongets(world, rng, mon, int(O.LEATHER_GLOVES))
        mongets(
            world,
            rng,
            mon,
            int(O.LEATHER_JACKET) if rng.rn2(2) else int(O.LEATHER_ARMOR),
        )
    elif mm == _pm("neanderthal"):
        mongets(world, rng, mon, int(O.CLUB))
        mongets(world, rng, mon, int(O.LEATHER_ARMOR))


def initthrow(world: World, rng, mon: Monster, otyp: int, oquan: int) -> None:
    """Give a monster a bundle of ammo (C: makemon.c#m_initthrow):
    ``rn1(oquan, 3)`` of them, in one stack."""
    from .invent import addinv  # local import: the makemon <- mkobj cycle
    from .mkobj import mksobj, weight  # local import: the mkobj cycle

    item = mksobj(world, rng, otyp, True, False)
    item.quan = rng.rn1(oquan, 3)
    item.owt = weight(world, item)
    # C: an orcish arrow is poisoned -- Item has no opoisoned yet
    addinv(world, mon.id, item)


def initinv(world: World, rng, mon: Monster) -> None:
    """The class-specific extras on top of the weapon kit (C:
    makemon.c#m_initinv, 588-833): a soldier's armour (aimed at the AC
    the species is supposed to have), a shopkeeper's key and stock, a
    priest's robe and purse, a nymp's mirror, a giant's gems, a
    leprechaun's gold, a gnome's candle.

    The same C order and the same draws.  Skipped (each named):
    ``Is_rogue_level()``; the quantmech's Schroedinger box's rot timer
    (the box and its cat are built, the corpse simply never rots); the
    gnome's ``begin_burn`` (no lamp system); the two muse.c tails
    (``rnd_defensive_item`` / ``rnd_misc_item`` -- their rolls are
    taken, no item is made).
    """
    from .invent import addinv  # local import: the makemon <- mkobj cycle
    from .mkobj import (  # local import: the mkobj cycle
        add_to_container,
        curse,
        mksobj,
        set_corpsenm,
        weight,
    )
    from .worn import arm_bonus  # local import: worn imports invent

    ptr = mon.mdata
    assert ptr is not None
    mm = ptr.pmidx

    if ptr.mlet == S_HUMAN:
        if is_mercenary(ptr):
            # C: the armour is chosen to approximate the species' AC
            mac = {
                _pm("guard"): -1,
                _pm("soldier"): 3,
                _pm("sergeant"): 0,
                _pm("lieutenant"): -2,
                _pm("captain"): -3,
                _pm("watchman"): 3,
                _pm("watch captain"): -2,
            }.get(mm, 0)

            def add_ac(item: Optional[Item]) -> None:
                nonlocal mac
                if item is not None:
                    mac += arm_bonus(item)

            # round 1: body armour
            if mac < -1 and rng.rn2(5):
                add_ac(
                    mongets_item(
                        world,
                        rng,
                        mon,
                        int(O.PLATE_MAIL) if rng.rn2(5) else int(O.CRYSTAL_PLATE_MAIL),
                    )
                )
            elif mac < 3 and rng.rn2(5):
                add_ac(
                    mongets_item(
                        world,
                        rng,
                        mon,
                        int(O.SPLINT_MAIL) if rng.rn2(3) else int(O.BANDED_MAIL),
                    )
                )
            elif rng.rn2(5):
                add_ac(
                    mongets_item(
                        world,
                        rng,
                        mon,
                        int(O.RING_MAIL) if rng.rn2(3) else int(O.STUDED_LEATHER_ARMOR),
                    )
                )
            else:
                add_ac(mongets_item(world, rng, mon, int(O.LEATHER_ARMOR)))
            # round 2: helmets
            if mac < 10 and rng.rn2(3):
                add_ac(mongets_item(world, rng, mon, int(O.HELMET)))
            elif mac < 10 and rng.rn2(2):
                add_ac(mongets_item(world, rng, mon, int(O.DENTED_POT)))
            # round 3: shields
            if mac < 10 and rng.rn2(3):
                add_ac(mongets_item(world, rng, mon, int(O.SMALL_SHIELD)))
            elif mac < 10 and rng.rn2(2):
                add_ac(mongets_item(world, rng, mon, int(O.LARGE_SHIELD)))
            # round 4: boots
            if mac < 10 and rng.rn2(3):
                add_ac(mongets_item(world, rng, mon, int(O.LOW_BOOTS)))
            elif mac < 10 and rng.rn2(2):
                add_ac(mongets_item(world, rng, mon, int(O.HIGH_BOOTS)))
            # round 5: gloves or a cloak
            if mac < 10 and rng.rn2(3):
                add_ac(mongets_item(world, rng, mon, int(O.LEATHER_GLOVES)))
            elif mac < 10 and rng.rn2(2):
                add_ac(mongets_item(world, rng, mon, int(O.LEATHER_CLOAK)))

            if mm == _pm("watch captain"):
                pass  # C: "better weapon rather than extra gear here"
            elif mm == _pm("watchman"):
                if rng.rn2(3):  # most watchmen carry a whistle
                    mongets(world, rng, mon, int(O.TIN_WHISTLE))
            elif mm == _pm("guard"):
                # C: the vault guard's whistle is cursed
                whistle = mksobj(world, rng, int(O.TIN_WHISTLE), True, False)
                curse(whistle)
                addinv(world, mon.id, whistle)
            else:  # soldiers and their officers
                if not rng.rn2(3):
                    mongets(world, rng, mon, int(O.K_RATION))
                if not rng.rn2(2):
                    mongets(world, rng, mon, int(O.C_RATION))
                if mm != _pm("soldier") and not rng.rn2(3):
                    mongets(world, rng, mon, int(O.BUGLE))
        elif mm == _pm("shopkeeper"):
            mongets(world, rng, mon, int(O.SKELETON_KEY))
            # C: a fall-through ladder -- the deeper the case, the more
            purse = rng.rn2(4)
            if purse == 0:
                mongets(world, rng, mon, int(O.WAN_MAGIC_MISSILE))
            if purse <= 1:
                mongets(world, rng, mon, int(O.POT_EXTRA_HEALING))
            if purse <= 2:
                mongets(world, rng, mon, int(O.POT_HEALING))
            mongets(world, rng, mon, int(O.WAN_STRIKING))
        elif ptr.msound == MS_PRIEST or _quest_role(ptr) == _pm("cleric"):
            mongets(
                world,
                rng,
                mon,
                (
                    int(O.ROBE)
                    if rng.rn2(7)
                    else (
                        int(O.CLOAK_OF_PROTECTION)
                        if rng.rn2(3)
                        else int(O.CLOAK_OF_MAGIC_RESISTANCE)
                    )
                ),
            )
            mongets(world, rng, mon, int(O.SMALL_SHIELD))
            mkmonmoney(world, rng, mon, rng.rn1(10, 20))
        elif _quest_role(ptr) == _pm("monk"):
            mongets(
                world,
                rng,
                mon,
                int(O.ROBE) if rng.rn2(11) else int(O.CLOAK_OF_MAGIC_RESISTANCE),
            )
    elif ptr.mlet == S_NYMPH:
        if not rng.rn2(2):
            mongets(world, rng, mon, int(O.MIRROR))
        if not rng.rn2(2):
            mongets(world, rng, mon, int(O.POT_OBJECT_DETECTION))
    elif ptr.mlet == S_GIANT:
        if mm == _pm("minotaur"):
            if not rng.rn2(8):
                mongets(world, rng, mon, int(O.WAN_DIGGING))
        elif is_giant(ptr):
            # a giant's purse of gems, one stack per point of half level
            for _ in range(rng.rn2(mon.m_lev // 2)):
                gems = mksobj(
                    world,
                    rng,
                    rnd_class_int(
                        world,
                        rng,
                        int(O.DILITHIUM_CRYSTAL),
                        int(O.LUCKSTONE) - 1,
                    ),
                    False,
                    False,
                )
                gems.quan = rng.rn1(2, 3)
                gems.owt = weight(world, gems)
                addinv(world, mon.id, gems)
    elif ptr.mlet == S_WRAITH:
        if mm == PM_NAZGUL:
            ring = mksobj(world, rng, int(O.RIN_INVISIBILITY), False, False)
            curse(ring)
            addinv(world, mon.id, ring)
    elif ptr.mlet == S_LICH:
        if mm == _pm("master lich") and not rng.rn2(13):
            mongets(
                world,
                rng,
                mon,
                int(O.ATHAME) if rng.rn2(7) else int(O.WAN_NOTHING),
            )
        elif mm == _pm("arch-lich") and not rng.rn2(3):
            staff = mksobj(
                world,
                rng,
                int(O.ATHAME) if rng.rn2(3) else int(O.QUARTERSTAFF),
                True,
                not rng.rn2(13),  # C: artif = rn2(13) == 0
            )
            if staff.spe < 2:
                staff.spe = rng.rnd(3)
            if not rng.rn2(4):
                staff.oerodeproof = True
            addinv(world, mon.id, staff)
    elif ptr.mlet == S_MUMMY:
        if rng.rn2(7):
            mongets(world, rng, mon, int(O.MUMMY_WRAPPING))
    elif ptr.mlet == S_QUANTMECH:
        if not rng.rn2(20) and mm == _pm("quantum mechanic"):
            # C: Schroedinger's box -- a large box with a house cat
            # corpse in it (the rot timer is the timeout system's)
            box = mksobj(world, rng, int(O.LARGE_BOX), False, False)
            cat = mksobj(world, rng, int(O.CORPSE), True, False)
            box.spe = 1  # the flag for a special Schroedinger's box
            set_corpsenm(world, cat, _pm("housecat"))
            add_to_container(world, box, cat)
            box.owt = weight(world, box)
            addinv(world, mon.id, box)
    elif ptr.mlet == S_LEPRECHAUN:
        mkmonmoney(world, rng, mon, rng.d(rules.level_difficulty(world), 30))
    elif ptr.mlet == S_DEMON:
        # C: these don't have AT_WEAP, so m_initweap is never called
        if mm == _pm("ice devil") and not rng.rn2(4):
            mongets(world, rng, mon, int(O.SPEAR))
        elif mm == _pm("Asmodeus"):
            mongets(world, rng, mon, int(O.WAN_COLD))
            mongets(world, rng, mon, int(O.WAN_FIRE))
    elif ptr.mlet == S_GNOME:
        if not rng.rn2(60):
            candle = mksobj(
                world,
                rng,
                int(O.TALLOW_CANDLE) if rng.rn2(4) else int(O.WAX_CANDLE),
                True,
                False,
            )
            candle.quan = 1
            candle.owt = weight(world, candle)
            addinv(world, mon.id, candle)
            # C: begin_burn(candle) when the square is unlit -- no lamp
            # system yet

    # C: ordinary soldiers rarely have access to magic (or gold :-)
    if mm == _pm("soldier") and rng.rn2(13):
        return

    # C: the two muse.c tails.  Their rolls are taken (the draw-order
    # rule); rnd_defensive_item / rnd_misc_item are not ported.
    mon.m_lev > rng.rn2(50)
    mon.m_lev > rng.rn2(100)
    if likes_gold(ptr) and not _has_gold(mon) and not rng.rn2(5):
        mkmonmoney(
            world,
            rng,
            mon,
            rng.d(rules.level_difficulty(world), 5 if mon.inventory else 10),
        )


def _has_gold(mon: Monster) -> bool:
    """C: findgold(mon->minvent) -- does the pack hold any coins?"""
    return any(it.oclass == int(ObjClass.COIN) for it in mon.inventory)


def _quest_role(ptr: PerMonst) -> int:
    """C: quest_mon_represents_role(ptr, pm) -- does this quest guardian
    stand in for that role's character class?  ``genus(mode=1)`` is
    exactly that mapping (mondata._GENUS_MAP plus the species rule), so
    the test is ``genus(ptr) == pm``.
    """
    return genus(ptr.pmidx, 1)


def mongets_item(world: World, rng, mon: Monster, otyp: int) -> Optional[Item]:
    """``mongets`` that answers the item (C: m_initinv's ``otmp =
    mongets(...)`` idiom -- the mercenary's ``add_ac(otmp)`` macro reads
    the armour's AC bonus as soon as it is made)."""
    item_id = mongets(world, rng, mon, otyp)
    if item_id is None:
        return None
    item = world.items.get(item_id)
    if item is None:
        return None
    return item


def rnd_class_int(world: World, rng, o_low: int, o_high: int) -> int:
    """C: rnd_class(o_low, o_high) -- re-exported from core.mkobj so a
    monster kit can pick a random object type (C calls it from
    m_initinv)."""
    from .mkobj import rnd_class  # local import: the mkobj cycle

    return rnd_class(world, rng, o_low, o_high)


__all__ = [
    "MAXMONNO",
    "MongenOrder",
    "STRAT_APPEARMSG",
    "STRAT_CLOSE",
    "STRAT_NONE",
    "STRAT_WAITFORU",
    "STRAT_WAITMASK",
    "adj_lev",
    "align_shift",
    "golemhp",
    "gen_ok",
    "initinv",
    "initthrow",
    "initweap",
    "is_home_elemental",
    "makemon",
    "mbirth_limit",
    "mkclass",
    "mkclass_aligned",
    "mkmonmoney",
    "monhp_per_lvl",
    "mongen_order",
    "mongets",
    "monmax_difficulty",
    "monmin_difficulty",
    "ndemon",
    "newmonhp",
    "peace_minded",
    "rnd_goodpos",
    "rndmonst",
    "rndmonst_adj",
    "set_malign",
    "temperature_shift",
    "uncommon",
]
