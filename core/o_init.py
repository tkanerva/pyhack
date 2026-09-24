"""Object table initialization and per-game object state (port of
src/o_init.c).

The static data lives in core.objects (frozen at import time, mirroring
the C `objects[]` initializer).  This module owns everything the C code
mutates in that array at runtime, gathered in one per-game `ObjTables`
state object (no globals, per the pyhack architecture):

- `bases`           -- C: svb.bases[], the start index of each class
- `prob`            -- current oc_prob (setgemprobs() adjusts gems)
- `prob_totals`     -- C: go.oclass_prob_totals[]
- `name_known`      -- C: objects[i].oc_name_known (discovered)
- `encountered`     -- C: objects[i].oc_encountered
- `uname`           -- C: objects[i].oc_uname (player-assigned names)
- `disco`           -- C: svd.disco[] (discovery order per class)
- `descr/color/material` -- per-otype, after description shuffling
- `wand_nothing_dir` -- C: objects[WAN_NOTHING].oc_dir, randomized

Dropped (window port, not game logic): the #known / #knownclass /
rename_disco display commands, tile shuffling, and savefile I/O
(savenames/restnames).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .objects import (ObjClass, ObjType, OBJECTS,
                     FIRST_OBJECT, LAST_REAL_GEM, MAXOCLASSES,
                     NODIR, IMMEDIATE, NUM_OBJECTS)

O = ObjType  # short alias for table lookups


# ------------------------------------------------------------
# Static: class base indices (C: init_objects() bases[] fill)
# ------------------------------------------------------------

def _compute_bases() -> List[int]:
    bases = [0] * (MAXOCLASSES + 2)
    first = MAXOCLASSES
    prevoclass = -1
    while first < NUM_OBJECTS:
        oclass = int(OBJECTS[first].oclass)
        if oclass < prevoclass:
            raise ValueError(
                f"objects[{first}] class #{oclass} not in order!")
        last = first + 1
        while last < NUM_OBJECTS and int(OBJECTS[last].oclass) == oclass:
            last += 1
        bases[oclass] = first
        first = last
        prevoclass = oclass
    bases[MAXOCLASSES] = bases[MAXOCLASSES + 1] = NUM_OBJECTS
    # guarantee no gaps (C: fill forward from the end)
    for last in range(MAXOCLASSES - 1, -1, -1):
        if not bases[last]:
            bases[last] = bases[last + 1]
    return bases


BASES: List[int] = _compute_bases()


# ------------------------------------------------------------
# Per-game state
# ------------------------------------------------------------

class ObjTables:
    """Mutable object state for one game (see module docstring)."""

    def __init__(self, rng):
        self.bases = list(BASES)
        self.prob = [o.prob for o in OBJECTS]
        self.prob_totals = [0] * MAXOCLASSES
        self.name_known: Set[int] = set()
        self.encountered: Set[int] = set()
        self.uname: Dict[int, str] = {}
        # discovery order, flat like C's svd.disco[]: within each class
        # range, non-None entries are the otyps in the order discovered
        self.disco: List[Optional[int]] = [None] * NUM_OBJECTS
        self.descr: List[Optional[str]] = [o.descr for o in OBJECTS]
        self.color: List[int] = [o.color for o in OBJECTS]
        self.material: List[int] = [int(o.material) for o in OBJECTS]
        self.wand_nothing_dir: int = NODIR
        init_objects(self, rng)

    # convenience: current description of an otyp (C: OBJ_DESCR)
    def descr_of(self, otyp: "ObjType | int") -> Optional[str]:
        if isinstance(otyp, ObjType):
            otyp = otyp.value
        return self.descr[otyp]


def _oclass_range(state: ObjTables, oclass: int) -> Tuple[int, int]:
    lo = state.bases[oclass]
    hi = state.bases[oclass + 1] - 1
    return lo, hi


# ------------------------------------------------------------
# Gem handling (C: setgemprobs, randomize_gem_colors)
# ------------------------------------------------------------

def setgemprobs(state: ObjTables, ledger_level: int = 0) -> None:
    """Level-dependent gem probabilities (C: setgemprobs).

    The most valuable gems stop appearing until the hero reaches a
    sufficient level: 9 - level/3 of the first gems get probability 0.
    """
    first = state.bases[int(ObjClass.GEM)]
    j = 0
    while j < 9 - ledger_level // 3:
        state.prob[first + j] = 0
        j += 1
    first += j
    if (first > LAST_REAL_GEM
            or int(OBJECTS[first].oclass) != int(ObjClass.GEM)
            or OBJECTS[first].name is None):
        raise ValueError(
            f"Not enough gems? first={first} j={j} LAST_GEM={LAST_REAL_GEM}")
    for idx in range(first, LAST_REAL_GEM + 1):
        state.prob[idx] = (171 + idx - first) // (LAST_REAL_GEM + 1 - first)
    # recompute GEM_CLASS total (including rocks/stones)
    lo, hi = _oclass_range(state, int(ObjClass.GEM))
    state.prob_totals[int(ObjClass.GEM)] = sum(state.prob[lo:hi + 1])


def randomize_gem_colors(state: ObjTables, rng) -> None:
    """Some gems can appear with different colors (C:
    randomize_gem_colors)."""
    def copy_descr(dst: int, src: int) -> None:
        state.descr[dst] = state.descr[src]
        state.color[dst] = state.color[src]

    if rng.rn2(2):  # change turquoise from green to blue?
        copy_descr(O.TURQUOISE.value, O.SAPPHIRE.value)
    if rng.rn2(2):  # change aquamarine from green to blue?
        copy_descr(O.AQUAMARINE.value, O.SAPPHIRE.value)
    # change fluorite from violet?
    case = rng.rn2(4)
    if case == 1:      # blue
        copy_descr(O.FLUORITE.value, O.SAPPHIRE.value)
    elif case == 2:    # white
        copy_descr(O.FLUORITE.value, O.DIAMOND.value)
    elif case == 3:    # green
        copy_descr(O.FLUORITE.value, O.EMERALD.value)


# ------------------------------------------------------------
# Description shuffling (C: shuffle, obj_shuffle_range, shuffle_all)
# ------------------------------------------------------------

def obj_shuffle_range(state: ObjTables, otyp: "ObjType | int") -> Tuple[int, int]:
    """The range of objects that `otyp` shares descriptions with
    (C: obj_shuffle_range)."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    ocls = int(OBJECTS[otyp].oclass)
    lo = hi = otyp

    if ocls == int(ObjClass.ARMOR):
        if O.HELMET.value <= otyp <= O.HELM_OF_TELEPATHY.value:
            lo, hi = O.HELMET.value, O.HELM_OF_TELEPATHY.value
        elif O.LEATHER_GLOVES.value <= otyp <= O.GAUNTLETS_OF_DEXTERITY.value:
            lo, hi = O.LEATHER_GLOVES.value, O.GAUNTLETS_OF_DEXTERITY.value
        elif (O.CLOAK_OF_PROTECTION.value <= otyp
                <= O.CLOAK_OF_DISPLACEMENT.value):
            lo, hi = (O.CLOAK_OF_PROTECTION.value,
                      O.CLOAK_OF_DISPLACEMENT.value)
        elif O.SPEED_BOOTS.value <= otyp <= O.LEVITATION_BOOTS.value:
            lo, hi = O.SPEED_BOOTS.value, O.LEVITATION_BOOTS.value
    elif ocls == int(ObjClass.POTION):
        # potion of water has the only fixed description
        lo, hi = state.bases[ocls], O.POT_WATER.value - 1
    elif ocls in (int(ObjClass.AMULET), int(ObjClass.SCROLL),
                  int(ObjClass.SPBOOK)):
        # exclude non-magic types and unique ones
        lo = state.bases[ocls]
        i = lo
        while (int(OBJECTS[i].oclass) == ocls
               and not OBJECTS[i].unique and OBJECTS[i].magic):
            i += 1
        hi = i - 1
    elif ocls in (int(ObjClass.RING), int(ObjClass.WAND),
                  int(ObjClass.VENOM)):
        # entire class
        lo, hi = _oclass_range(state, ocls)

    if otyp < lo or otyp > hi:
        lo = hi = otyp
    return lo, hi


def shuffle(state: ObjTables, rng, o_low: int, o_high: int,
            domaterial: bool) -> None:
    """Shuffle descriptions on objects o_low..o_high (C: shuffle).

    Objects whose names are already known don't move; the descr/color
    (and optionally material) of the rest are permuted.
    """
    num_to_shuffle = sum(1 for j in range(o_low, o_high + 1)
                         if j not in state.name_known)
    if num_to_shuffle < 2:
        return
    for j in range(o_low, o_high + 1):
        if j in state.name_known:
            continue
        i = j + rng.rn2(o_high - j + 1)
        while i in state.name_known:
            i = j + rng.rn2(o_high - j + 1)
        state.descr[j], state.descr[i] = state.descr[i], state.descr[j]
        state.color[j], state.color[i] = state.color[i], state.color[j]
        if domaterial:
            state.material[j], state.material[i] = \
                state.material[i], state.material[j]


def shuffle_all(state: ObjTables, rng) -> None:
    """Randomize object descriptions (C: shuffle_all)."""
    # whole classes (obj_shuffle_range() handles their exceptions)
    for ocls in (int(ObjClass.AMULET), int(ObjClass.POTION),
                 int(ObjClass.RING), int(ObjClass.SCROLL),
                 int(ObjClass.SPBOOK), int(ObjClass.WAND),
                 int(ObjClass.VENOM)):
        lo, hi = obj_shuffle_range(state, state.bases[ocls])
        shuffle(state, rng, lo, hi, True)
    # sub-class type ranges (one representative from each group)
    for otyp in (O.HELMET, O.LEATHER_GLOVES, O.CLOAK_OF_PROTECTION,
                 O.SPEED_BOOTS):
        lo, hi = obj_shuffle_range(state, otyp)
        shuffle(state, rng, lo, hi, False)


# ------------------------------------------------------------
# Class probability totals (C: init_oclass_probs)
# ------------------------------------------------------------

def init_oclass_probs(state: ObjTables) -> None:
    for oclass in range(MAXOCLASSES):
        lo, hi = _oclass_range(state, oclass)
        total = sum(state.prob[lo:hi + 1])
        if total <= 0 and oclass != int(ObjClass.ILLOBJ) \
                and state.bases[oclass] != state.bases[oclass + 1]:
            raise ValueError(
                f"{'zero' if not total else 'negative'} "
                f"probability total for oclass {oclass}")
            # C repairs by giving every member probability 1; we fail
            # loudly instead (a data error, not a game condition)
        state.prob_totals[oclass] = total


# ------------------------------------------------------------
# Full initialization (C: init_objects, oinit)
# ------------------------------------------------------------

def init_objects(state: ObjTables, rng) -> None:
    # slots [1..17] must be the generic class placeholders
    for i in range(1, MAXOCLASSES):
        if int(OBJECTS[i].oclass) != i:
            raise ValueError(
                f"init_objects: class for generic object #{i} doesn't "
                f"match ({OBJECTS[i].oclass})")
    # check oc_name_known vs. presence of an alternate description
    # (C: no-description items must be pre-known, described items must
    # not be; a contradiction is a table error)
    for i in range(MAXOCLASSES, NUM_OBJECTS):
        nmkn = 1 if OBJECTS[i].name_known else 0
        if (OBJECTS[i].descr is None) ^ bool(nmkn):
            raise ValueError(
                f"obj #{i} name state contradicts its alternate "
                f"description (name_known={nmkn})")
    # level-0 gem probabilities and gem color randomization
    setgemprobs(state)
    randomize_gem_colors(state, rng)
    # compute oclass probability totals
    init_oclass_probs(state)
    # shuffle descriptions
    shuffle_all(state, rng)
    # the wand of nothing can work either way (C does this last)
    state.wand_nothing_dir = NODIR if rng.rn2(2) else IMMEDIATE


def oinit(state: ObjTables, rng, ledger_level: int = 0) -> None:
    """Level-dependent initialization when entering a level (C: oinit)."""
    setgemprobs(state, ledger_level)


# ------------------------------------------------------------
# Discovery tracking (C: observe_object, discover_object,
# undiscover_object, interesting_to_discover)
# ------------------------------------------------------------

def discover_object(state: ObjTables, otyp: "ObjType | int",
                    mark_as_known: bool, mark_as_encountered: bool,
                    credit_hero: bool = False) -> bool:
    """Record a discovery; returns True if anything changed
    (C: discover_object).  `credit_hero` is the hook for
    exercise(A_WIS) -- callers decide what it means."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    if otyp < FIRST_OBJECT:  # don't discover generic objects
        return False

    changed = False
    if otyp not in state.encountered and mark_as_encountered:
        state.encountered.add(otyp)
        changed = True
    if otyp not in state.name_known and mark_as_known:
        state.name_known.add(otyp)
        # find the target slot (which may have been discovered earlier)
        # or the next open one within the class range
        ocls = int(OBJECTS[otyp].oclass)
        dindx = state.bases[ocls]
        while state.disco[dindx] is not None and state.disco[dindx] != otyp:
            dindx += 1
        state.disco[dindx] = otyp
        changed = True
    return changed


def observe_object(state: ObjTables, otyp: "ObjType | int") -> bool:
    """An object is seen up close: mark dknown and encountered
    (C: observe_object)."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    if otyp >= FIRST_OBJECT:
        return discover_object(state, otyp, False, True)
    return False


def undiscover_object(state: ObjTables, otyp: "ObjType | int") -> None:
    """Purge a discovery that is no longer known or encountered
    (C: undiscover_object)."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    if otyp in state.name_known or otyp in state.encountered:
        return
    ocls = int(OBJECTS[otyp].oclass)
    found = False
    dindx = state.bases[ocls]
    while (dindx < NUM_OBJECTS and state.disco[dindx] is not None
           and int(OBJECTS[dindx].oclass) == ocls):
        if found:
            state.disco[dindx - 1] = state.disco[dindx]
        elif state.disco[dindx] == otyp:
            found = True
        dindx += 1
    if found:
        state.disco[dindx - 1] = None
    else:
        raise ValueError("named object not in disco")


def interesting_to_discover(state: ObjTables, otyp: "ObjType | int") -> bool:
    """Should this type show in the discoveries list
    (C: interesting_to_discover)."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    return (otyp in state.uname
            or ((otyp in state.name_known or otyp in state.encountered)
                and state.descr[otyp] is not None))


def typename(state: ObjTables, otyp: "ObjType | int") -> str:
    """The name (if known, or user-assigned), else the current
    (possibly shuffled) description (C: obj_typename, simplified)."""
    if isinstance(otyp, ObjType):
        otyp = otyp.value
    if otyp in state.uname:
        return state.uname[otyp]
    if otyp in state.name_known or OBJECTS[otyp].name_known:
        return OBJECTS[otyp].name
    descr = state.descr[otyp]
    return descr if descr is not None else "strange object"
