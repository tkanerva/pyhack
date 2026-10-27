"""Tests for the hunger system (core/hunger.py, the eat.c port).

House conventions: table-driven over the C branches, SeqRng presets
the exact dice (the draws are the commented C rn2 / rnd sites in
core/hunger.py, in C order), and every test asserts world state
*and* the event list.

C provenance (NetHack 5.0, local clone at ../NetHack): src/eat.c
(gethungry, newuhs, unfaint, lesshungry, morehungry, choke, doeat,
fprefx, hu_stat), src/botl.c (the bottom-line text), src/spell.c
(spelleffects_check's "too hungry" gate), include/hack.h (the
hunger_state_types enum values).  The C rn2(n) draws (0..n-1) are the
1-based SeqRng values shifted: a `!rn2(n)` site fires on 1, a
`rn2(n) == k` site fires on k + 1.
"""
import pytest

from core import EatCommand, HungerState, MoveCommand, SpellType, step
from core.events import DeathEvent, MessageEvent
from core.hunger import (HU_STAT, choke, eat_food, hunger_state,
                         init_uhunger, lesshungry, morehungry, newuhs,
                         tick_hunger)
from core.objects import (ObjClass, ObjType, Prop, W_AMUL, W_RINGL,
                          W_RINGR, W_TOOL, object_type)
from core.rules import current_ability, tick_actor
from core.spells import cast_spell
from core.types import Item, ObjectType
from conftest import SeqRng, make_world

O = ObjType
SATIATED = HungerState.SATIATED
NOT_HUNGRY = HungerState.NOT_HUNGRY
HUNGRY = HungerState.HUNGRY
WEAK = HungerState.WEAK
FAINTING = HungerState.FAINTING
FAINTED = HungerState.FAINTED
STARVED = HungerState.STARVED


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------

def make_food(otyp, id="food_0", cursed=False, blessed=False, **kw):
    it = Item(id=id, otype=ObjectType.FOOD, name=object_type(otyp).name,
              otyp=otyp.value, oclass=ObjClass.FOOD.value,
              cursed=cursed, blessed=blessed, **kw)
    return it


def add_food(w, it):
    it.container = "player"
    w.items[it.id] = it
    w.hero.inventory.append(it)
    return it


def make_ring(otyp, spe=0, mask=W_RINGL, id="ring_0", **kw):
    it = Item(id=id, otype=ObjectType.RING, name=object_type(otyp).name,
              otyp=otyp.value, oclass=ObjClass.RING.value, spe=spe, **kw)
    it.owornmask = mask
    return it


def make_amulet(otyp, mask=W_AMUL, id="amul_0"):
    it = Item(id=id, otype=ObjectType.AMULET,
              name=object_type(otyp).name, otyp=otyp.value,
              oclass=ObjClass.AMULET.value)
    it.owornmask = mask
    return it


def wear(w, it):
    w.items[it.id] = it
    w.hero.inventory.append(it)
    return it


def sword():
    sw = Item(id="sword_0", otype=ObjectType.WEAPON, name="short sword",
              otyp=O.SHORT_SWORD.value, oclass=ObjClass.WEAPON.value)
    return sw


def set_hunger(w, h, uhs=None, fainted=0):
    w.hero.uhunger = h
    w.hero.uhs = uhs if uhs is not None else hunger_state(h)
    w.hero.fainted = fainted


def texts(ev):
    return [e.text for e in ev if isinstance(e, MessageEvent)]


# ------------------------------------------------------------
# the data: the C enum values and the botl texts
# ------------------------------------------------------------

def test_hunger_state_enum_keeps_the_c_values():
    """C: the hunger_state_types enum (include/hack.h)."""
    assert (SATIATED, NOT_HUNGRY, HUNGRY, WEAK, FAINTING, FAINTED,
            STARVED) == (0, 1, 2, 3, 4, 5, 6)


def test_hu_stat_is_the_c_table():
    """C: the hu_stat[] texts of eat.c (printed by botl.c when
    uhs != NOT_HUNGRY), padding and all."""
    assert HU_STAT == ("Satiated", "        ", "Hungry  ", "Weak    ",
                       "Fainting", "Fainted ", "Starved ")


def test_monster_defaults_are_the_c_start():
    """C: init_uhunger -- start 900 / NOT_HUNGRY (u_init.c)."""
    w = make_world()
    assert w.hero.uhunger == 900
    assert w.hero.uhs == NOT_HUNGRY
    assert w.hero.fainted == 0


# ------------------------------------------------------------
# hunger_state (the newuhs threshold step)
# ------------------------------------------------------------

@pytest.mark.parametrize("h,expected", [
    (2000, SATIATED), (1001, SATIATED),   # C: h > 1000 -> SATIATED
    (1000, NOT_HUNGRY), (151, NOT_HUNGRY),  # C: h > 150 -> NOT_HUNGRY
    (150, HUNGRY), (51, HUNGRY),            # C: h > 50 -> HUNGRY
    (50, WEAK), (1, WEAK),                  # C: h > 0 -> WEAK
    (0, FAINTING), (-50, FAINTING),         # C: else FAINTING
])
def test_hunger_state_thresholds(h, expected):
    assert hunger_state(h) == expected


# ------------------------------------------------------------
# init_uhunger
# ------------------------------------------------------------

def test_init_uhunger_restores_the_gauge():
    """C: init_uhunger (hero init, life-saving, prayer results)."""
    w = make_world()
    set_hunger(w, -50, uhs=FAINTED, fainted=10)
    init_uhunger(w, "player")
    assert w.hero.uhunger == 900
    assert w.hero.uhs == NOT_HUNGRY


# ------------------------------------------------------------
# newuhs: the state-change messages (the <145 / <45 splits)
# ------------------------------------------------------------

def test_newuhs_hungry_messages():
    w = make_world()
    # entering HUNGRY while the gauge falls (incr=True):
    set_hunger(w, 145, uhs=NOT_HUNGRY)
    assert texts(newuhs(w, "player", True, SeqRng())) \
        == ["You are beginning to feel hungry."]
    assert w.hero.uhs == HUNGRY
    set_hunger(w, 144, uhs=NOT_HUNGRY)
    assert texts(newuhs(w, "player", True, SeqRng())) \
        == ["You feel hungry."]
    # entering HUNGRY while the gauge rises (incr=False):
    set_hunger(w, 100, uhs=WEAK)
    assert texts(newuhs(w, "player", False, SeqRng())) \
        == ["You only feel hungry now."]
    assert w.hero.uhs == HUNGRY


def test_newuhs_weak_messages():
    w = make_world()
    set_hunger(w, 50, uhs=HUNGRY)
    assert texts(newuhs(w, "player", True, SeqRng())) \
        == ["You are beginning to feel weak."]
    assert w.hero.uhs == WEAK
    set_hunger(w, 44, uhs=HUNGRY)
    assert texts(newuhs(w, "player", True, SeqRng())) \
        == ["You feel weak."]
    set_hunger(w, 44, uhs=HUNGRY)
    assert texts(newuhs(w, "player", False, SeqRng())) \
        == ["You are still weak."]


def test_newuhs_no_message_without_state_change():
    w = make_world()
    set_hunger(w, 160, uhs=NOT_HUNGRY)
    assert newuhs(w, "player", True, SeqRng()) == []
    set_hunger(w, 1000, uhs=NOT_HUNGRY)
    assert texts(newuhs(w, "player", False, SeqRng())) == []
    assert w.hero.uhs == NOT_HUNGRY   # 1000 is not > 1000
    set_hunger(w, 1001, uhs=NOT_HUNGRY)
    assert texts(newuhs(w, "player", False, SeqRng())) == []
    assert w.hero.uhs == SATIATED


# ------------------------------------------------------------
# newuhs: the faint (C: the FAINTING branch)
# ------------------------------------------------------------

def test_newuhs_first_faint_needs_no_roll():
    """C: `u.uhs <= WEAK` -> the faint fires without the roll;
    duration 10 - div, div 0 at h 0.  No dice at all."""
    w = make_world()
    set_hunger(w, 0, uhs=WEAK)
    ev = newuhs(w, "player", True, SeqRng())
    assert texts(ev) == ["You faint from lack of food."]
    assert w.hero.uhs == FAINTED
    assert w.hero.fainted == 10


def test_newuhs_faint_duration_grows_with_the_deficit():
    """C: div = sgn(h) * ((abs(h) + 5) / 10) -- negative for h < 0,
    so the deeper the deficit the LONGER the faint."""
    w = make_world()
    set_hunger(w, -50, uhs=WEAK)       # div = -5 -> 10 - (-5) = 15
    newuhs(w, "player", True, SeqRng())
    assert w.hero.fainted == 15
    assert w.hero.uhs == FAINTED


def test_newuhs_faint_roll_path():
    """C: `rn2(20 - div) >= 19` -- the 0-based draw is 19 1 in 20 at
    div 0 (here div -2, 1 in 22), the 1-based draw fires on its top
    value."""
    w = make_world()
    set_hunger(w, -20, uhs=FAINTING)   # div -2 -> rn2(22)
    newuhs(w, "player", True, SeqRng(22))
    assert w.hero.uhs == FAINTED
    assert w.hero.fainted == 12        # 10 - (-2)
    set_hunger(w, -20, uhs=FAINTING)
    assert newuhs(w, "player", True, SeqRng(18)) == []
    assert w.hero.uhs == FAINTING
    assert w.hero.fainted == 0


def test_newuhs_fainted_stays_fainted():
    """C: is_fainted() -> newhs = FAINTED; a successful re-roll
    neither re-messages nor extends the counter."""
    w = make_world()
    set_hunger(w, -20, uhs=FAINTED, fainted=7)
    assert newuhs(w, "player", True, SeqRng(22)) == []
    assert w.hero.uhs == FAINTED
    assert w.hero.fainted == 7


def test_newuhs_starvation():
    """C: `u.uhunger < -(100 + 10 * ACURR(A_CON))` -> the starvation
    death (done(STARVING), killer "starvation").  CON 12 -> floor
    -220; the faint roll must fail first (it is the C elif)."""
    w = make_world()
    set_hunger(w, -221, uhs=FAINTING)  # div -22 -> rn2(42)
    ev = newuhs(w, "player", True, SeqRng(1))
    assert texts(ev) == ["You die from starvation.", "💀 You are dead!"]
    assert w.hero.uhs == STARVED
    assert not w.hero.alive and w.hero.hp == 0
    deaths = [e for e in ev if isinstance(e, DeathEvent)]
    assert len(deaths) == 1 and deaths[0].by == "starvation"


def test_newuhs_starvation_floor_reads_the_current_con():
    """C: ACURR(A_CON) -- a worn +1 constitution ring moves the floor
    from -220 to -230, so -221 no longer kills."""
    w = make_world()
    wear(w, make_ring(O.RIN_GAIN_CONSTITUTION, spe=1))
    assert current_ability(w.hero, "con") == 13
    set_hunger(w, -221, uhs=FAINTING)
    assert newuhs(w, "player", True, SeqRng(1)) == []
    assert w.hero.alive
    assert w.hero.uhs == FAINTING


def test_newuhs_exhaustion_guard():
    """C: after a state change, `if (u.uhp < 1)` -> "You die from
    hunger and exhaustion." (the port reaches it on a dead-but-still-
    -living hero; normally apply_damage has already killed)."""
    w = make_world()
    set_hunger(w, 44, uhs=HUNGRY)
    w.hero.hp = 0                      # inconsistent state, for the guard
    ev = newuhs(w, "player", True, SeqRng())
    assert texts(ev) == ["You feel weak.",
                         "You die from hunger and exhaustion."]
    assert w.hero.uhs == STARVED       # the port's death bookkeeping


# ------------------------------------------------------------
# the faint countdown (rules.tick_actor + the step gate)
# ------------------------------------------------------------

def test_tick_actor_faint_countdown():
    w = make_world()
    set_hunger(w, 0, uhs=FAINTED, fainted=2)
    assert tick_actor(w, "player", SeqRng()) == []
    assert w.hero.fainted == 1
    assert w.hero.uhs == FAINTED
    ev = tick_actor(w, "player", SeqRng())
    assert texts(ev) == ["You regain consciousness."]
    assert w.hero.fainted == 0
    # C: unfaint() -- if (u.uhs > FAINTING) u.uhs = FAINTING
    assert w.hero.uhs == FAINTING


def test_step_fainted_hero_takes_no_action():
    w = make_world()
    set_hunger(w, 0, uhs=FAINTED, fainted=5)
    # the metabolism draw (9: no slow-metabolism decrement), then the
    # faint roll (1: fail -- h 0 is nowhere near the starvation floor)
    ev = step(w, MoveCommand(1, 0), SeqRng(9, 1))
    assert w.hero.pos == (6, 4)
    assert w.hero.fainted == 4         # the tick, not the action, moved it
    assert w.hero.uhunger == 0
    assert ev == []


def test_step_fainted_hero_recovers_and_acts():
    """C: the faint's nomul ends DURING the round (afternmv) -- the
    recovery round is a no-action round, the action resumes the round
    after (the gate is computed before the tick)."""
    w = make_world()
    set_hunger(w, 0, uhs=FAINTED, fainted=1)
    # the faint roll (1: the faint does not re-fire) -- the counter
    # hit 0 in tick_actor, so the metabolism draw is not made
    ev = step(w, MoveCommand(1, 0), SeqRng(1))
    assert texts(ev) == ["You regain consciousness."]
    assert w.hero.pos == (6, 4)         # the recovery round is a pass
    assert w.hero.uhs == FAINTING
    assert w.hero.uhunger == -1         # the ticker ran this round
    ev = step(w, MoveCommand(1, 0), SeqRng(1))
    assert w.hero.pos == (7, 4)         # the gate opened
    assert w.hero.uhunger == -2


# ------------------------------------------------------------
# tick_hunger (C: gethungry) -- the main decrement
# ------------------------------------------------------------

def test_tick_hunger_bare_hero_costs_one_and_no_draws():
    """The house zero-draw path (PLAN-HUNGER.md decision 4): no
    intrinsics, no worn ring / amulet, no carried real Amulet -> the
    accessory draw is skipped; the bare SeqRng proves it."""
    w = make_world()
    set_hunger(w, 900)
    assert tick_hunger(w, "player", SeqRng()) == []
    assert w.hero.uhunger == 899


def test_tick_hunger_dead_hero_is_skipped():
    w = make_world()
    set_hunger(w, 900)
    w.hero.alive = False
    assert tick_hunger(w, "player", SeqRng()) == []
    assert w.hero.uhunger == 900


def test_tick_hunger_fainted_slow_metabolism():
    """C: `(!Unaware || !rn2(10))` -- fainted, the decrement happens
    1 in 10 (the 0-based draw is zero, the 1-based fires on 1)."""
    w = make_world()
    set_hunger(w, 900, fainted=5)
    tick_hunger(w, "player", SeqRng(1))
    assert w.hero.uhunger == 899
    set_hunger(w, 900, fainted=5)
    tick_hunger(w, "player", SeqRng(9))
    assert w.hero.uhunger == 900


# ------------------------------------------------------------
# tick_hunger -- the accessory branches (the even cases 0/4/8/12/16)
# ------------------------------------------------------------

def test_tick_hunger_odd_regeneration():
    """C: the odd accessorytime burns the REGENERATION property (the
    draw is randint-1, so the even 1-based values are C's odd)."""
    w = make_world()
    w.hero.intrinsics = {Prop.REGENERATION}
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(2))      # C accessorytime 1 (odd)
    assert w.hero.uhunger == 898
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(5))      # C accessorytime 4 (even)
    assert w.hero.uhunger == 899


def test_tick_hunger_even_hunger_property():
    """C: the even accessorytime burns the Hunger property (dragon
    skins) -- the ported intrinsics-only read (PLAN-HUNGER.md 5.2)."""
    w = make_world()
    w.hero.intrinsics = {Prop.HUNGER}
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(5))      # C accessorytime 4 (even)
    assert w.hero.uhunger == 898
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(2))      # C accessorytime 1 (odd)
    assert w.hero.uhunger == 899


def test_tick_hunger_even_conflict_property():
    w = make_world()
    w.hero.intrinsics = {Prop.CONFLICT}
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(7))      # C accessorytime 6 (even)
    assert w.hero.uhunger == 898


def test_tick_hunger_case0_slow_digestion_armor():
    """C case 0: slow digestion from worn armor (not a ring of slow
    digestion) burns the turn."""
    w = make_world()
    w.hero.intrinsics = {Prop.SLOW_DIGESTION}
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(1))      # C accessorytime 0
    assert w.hero.uhunger == 898
    # a ring of slow digestion suppresses the armor case (C: the
    # uleft / uright RIN_SLOW_DIGESTION check)
    w.hero.intrinsics = set()
    wear(w, make_ring(O.RIN_SLOW_DIGESTION, mask=W_RINGL))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(1))
    assert w.hero.uhunger == 899


def test_tick_hunger_case4_left_ring():
    """C case 4: the worn left ring burns if spe != 0 or its type is
    not oc_charged, MEAT_RING excepted (the EProtection +0 special
    case is dropped, PLAN-HUNGER.md 4)."""
    w = make_world()
    wear(w, make_ring(O.RIN_PROTECTION, spe=1, mask=W_RINGL))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(5))      # C accessorytime 4
    assert w.hero.uhunger == 898
    # a +0 charged ring does nothing (the ported condition)
    w = make_world()
    wear(w, make_ring(O.RIN_PROTECTION, spe=0, mask=W_RINGL))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(5))
    assert w.hero.uhunger == 899
    # a worn meat ring never burns (5.0: no hunger penalty)
    w = make_world()
    wear(w, make_ring(O.MEAT_RING, mask=W_RINGL))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(5))
    assert w.hero.uhunger == 899


def test_tick_hunger_case8_worn_amulet():
    """C case 8: the worn amulet burns, a FAKE amulet never (5.0)."""
    w = make_world()
    wear(w, make_amulet(O.AMULET_OF_YENDOR, mask=W_AMUL))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(9))      # C accessorytime 8
    assert w.hero.uhunger == 898
    w = make_world()
    wear(w, make_amulet(O.FAKE_AMULET_OF_YENDOR, mask=W_AMUL))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(9))
    assert w.hero.uhunger == 899


def test_tick_hunger_case12_right_ring():
    w = make_world()
    wear(w, make_ring(O.RIN_PROTECTION, spe=1, mask=W_RINGR))
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(13))     # C accessorytime 12
    assert w.hero.uhunger == 898


def test_tick_hunger_case16_carried_real_amulet():
    """C case 16: possessing (carrying) the real Amulet is a separate
    penalty from wearing it (u.uhave.amulet)."""
    w = make_world()
    am = make_amulet(O.AMULET_OF_YENDOR, mask=0)
    am.container = "player"
    w.items[am.id] = am
    w.hero.inventory.append(am)
    set_hunger(w, 900)
    tick_hunger(w, "player", SeqRng(17))     # C accessorytime 16
    assert w.hero.uhunger == 898


# ------------------------------------------------------------
# lesshungry / morehungry / choke
# ------------------------------------------------------------

def test_lesshungry_rises_the_gauge():
    w = make_world()
    set_hunger(w, 150, uhs=HUNGRY)
    ev = lesshungry(w, "player", 100, SeqRng())
    assert texts(ev) == []                  # HUNGRY->NOT_HUNGRY: no line
    assert w.hero.uhunger == 250
    assert w.hero.uhs == NOT_HUNGRY


def test_lesshungry_fullwarn_line():
    """C: the >=1500 line, once, suppressed by the Hunger property."""
    w = make_world()
    set_hunger(w, 1400)
    ev = lesshungry(w, "player", 300, SeqRng())
    assert texts(ev) == ["You're having a hard time getting all of it down."]
    assert w.hero.uhunger == 1700
    w.hero.intrinsics = {Prop.HUNGER}
    set_hunger(w, 1400)
    assert texts(lesshungry(w, "player", 300, SeqRng())) == []


def test_lesshungry_choke_survives_one_in_twenty():
    """C: >=2000 chokes when the pre-meal state was SATIATED; the
    `!rn2(20)` survive roll is 1 in 20 -- vomit + morehungry(1000)."""
    w = make_world()
    set_hunger(w, 1950, uhs=SATIATED)
    ev = lesshungry(w, "player", 50, SeqRng(1))
    assert texts(ev) == ["You stuff yourself and then vomit voluminously."]
    assert w.hero.uhunger == 1000            # 2000 - 1000
    assert w.hero.uhs == NOT_HUNGRY          # 1000 is not > 1000
    assert w.hero.alive


def test_lesshungry_choke_dies_nineteen_in_twenty():
    """C: the else branch -- choking is in C nearly always fatal."""
    w = make_world()
    set_hunger(w, 1950, uhs=SATIATED)
    ev = lesshungry(w, "player", 50, SeqRng(2))
    # C: choke(0) -- no food pointer -> "You choke over it."
    assert texts(ev) == ["You choke over it.", "You die...",
                         "💀 You are dead!"]
    assert not w.hero.alive
    assert w.hero.uhs == SATIATED


def test_choke_needs_the_satiated_pre_meal_state():
    """C: the `u.uhs != SATIATED` early-return (the canchoke gate) --
    a NOT_HUNGRY hero at 2000 is merely satiated, not choking."""
    w = make_world()
    set_hunger(w, 1950, uhs=NOT_HUNGRY)
    ev = lesshungry(w, "player", 50, SeqRng())
    assert ev == []
    assert w.hero.uhunger == 2000
    assert w.hero.uhs == SATIATED


def test_morehungry_drops_the_gauge():
    """C: morehungry(num) -- after vomiting / feats of magic.  The
    fall from 200 to -800 is a first faint (uhs NOT_HUNGRY <= WEAK,
    no roll); div = sgn(-800) * ((800 + 5) / 10) = -80 -> 90 turns."""
    w = make_world()
    set_hunger(w, 200)
    ev = morehungry(w, "player", 1000, SeqRng())
    assert texts(ev) == ["You faint from lack of food."]
    assert w.hero.uhunger == -800
    assert w.hero.uhs == FAINTED
    assert w.hero.fainted == 90


# ------------------------------------------------------------
# eat_food (C: the doeat food subset)
# ------------------------------------------------------------

def test_eat_food_not_carried():
    w = make_world()
    ev = eat_food(w, "player", "nope", SeqRng())
    assert texts(ev) == ["You don't have such food."]


def test_eat_food_floor_item_rejected():
    """C: floorfood() selection is unported (the command names the
    item, like ReadCommand); a floor item is simply not found."""
    w = make_world()
    ap = make_food(O.APPLE)
    ap.container = None
    ap.pos = (3, 3)
    w.items[ap.id] = ap
    ev = eat_food(w, "player", ap.id, SeqRng())
    assert texts(ev) == ["You don't have such food."]
    assert ap.pos == (3, 3)                 # untouched


def test_eat_nonfood_refused():
    """C: is_edible() -> "You cannot eat that!" (the fixed-human
    subset: the FOOD_CLASS test)."""
    w = make_world()
    sw = sword()
    sw.container = "player"
    w.items[sw.id] = sw
    w.hero.inventory.append(sw)
    ev = eat_food(w, "player", sw.id, SeqRng())
    assert texts(ev) == ["You cannot eat that!"]
    assert sw in w.hero.inventory


def test_eat_worn_item_refused():
    """C: the worn-food refusal (owornmask & (W_ARMOR | W_TOOL |
    W_AMUL)); rings are let through in C (the demo has no edible
    rings, so any mask on a food is the refusal)."""
    w = make_world()
    ap = make_food(O.APPLE, owornmask=W_TOOL)
    add_food(w, ap)
    ev = eat_food(w, "player", ap.id, SeqRng())
    assert texts(ev) == ["You can't eat something you're wearing."]
    assert ap in w.hero.inventory
    assert w.hero.uhunger == 900


def test_eat_apple_delicious():
    """C: the give_feedback default -- the whole item, full nutrition
    (50), one turn (the one-turn meal, PLAN-HUNGER.md decision 5)."""
    w = make_world()
    ap = add_food(w, make_food(O.APPLE))
    ev = eat_food(w, "player", ap.id, SeqRng())
    assert texts(ev) == ["This apple is delicious!"]
    assert w.hero.uhunger == 950
    assert ap not in w.hero.inventory
    assert w.items.get(ap.id) is None


def test_eat_cursed_food_terrible():
    """C: the cursed half of give_feedback."""
    w = make_world()
    ap = add_food(w, make_food(O.APPLE, cursed=True))
    ev = eat_food(w, "player", ap.id, SeqRng())
    assert texts(ev) == ["This apple is terrible!"]
    assert w.hero.uhunger == 950


def test_eat_bland_rations():
    """C: the CRAM / K / C ration half of give_feedback, the meal as
    the C occupation (PLAN-OCCUPATION.md): the K / C rations are the
    delay 1 one-bite pieces (unchanged behaviour); the CRAM ration
    (delay 3, nutrition 600) eats its first bite (200) on the command
    turn and the rest runs as the occupation."""
    for otyp in (O.CRAM_RATION, O.K_RATION, O.C_RATION):
        w = make_world()
        r = add_food(w, make_food(otyp))
        set_hunger(w, 200)
        ev = eat_food(w, "player", r.id, SeqRng())
        assert texts(ev) == [f"This {object_type(otyp).name} is bland."], otyp
        if otyp == O.CRAM_RATION:
            assert w.hero.uhunger == 400             # 200 + 600/3
            assert r.oeaten == 200
            assert w.occupation is not None
        else:
            assert w.hero.uhunger == 200 + object_type(otyp).nutrition
            assert r not in w.hero.inventory
            assert w.occupation is None


def test_eat_food_ration_tiers():
    """C: the FOOD_RATION cases of fprefx (nutrition 800): the
    <=200 / <700 / else split, on the pre-meal gauge.  The meal is
    the C occupation: the first bite is 160 on the command turn, the
    rest one per round -- the fullwarning line (>= 1500) is crossed
    only by the LAST bite of the 800-start meal."""
    from core.occupation import run_occupation
    w = make_world()
    r = add_food(w, make_food(O.FOOD_RATION))
    set_hunger(w, 200)
    ev = eat_food(w, "player", r.id, SeqRng())
    assert texts(ev) == ["This food really hits the spot!"]
    assert w.hero.uhunger == 360                   # 200 + 160
    w = make_world()
    r = add_food(w, make_food(O.FOOD_RATION))
    set_hunger(w, 500)
    ev = eat_food(w, "player", r.id, SeqRng())
    assert texts(ev) == ["This satiates your stomach!"]
    assert w.hero.uhunger == 660                   # 500 + 160
    w = make_world()
    r = add_food(w, make_food(O.FOOD_RATION))
    set_hunger(w, 800)
    ev = eat_food(w, "player", r.id, SeqRng())
    # above 700: no fprefx feedback; the first bite lands at 960
    assert texts(ev) == []
    assert w.hero.uhunger == 960
    for _ in range(3):
        ev = run_occupation(w, SeqRng())
        assert texts(ev) == []
    ev = run_occupation(w, SeqRng())
    # the last bite (1440 -> 1600) crosses the 1500 fullwarning line
    assert texts(ev) == ["You're having a hard time getting all of it down.",
                         "You finish eating the food ration."]
    assert w.hero.uhunger == 1600


def test_eat_tripe_ration():
    """C: the human (non-carnivorous, humanoid) branch of fprefx; the
    tripe ration (delay 2, nutrition 200) is the first multi-bite
    piece of the demo kit: first bite 100 on the command turn, the
    rest runs as the occupation."""
    from core.occupation import run_occupation
    w = make_world()
    t = add_food(w, make_food(O.TRIPE_RATION))
    ev = eat_food(w, "player", t.id, SeqRng())
    assert texts(ev) == ["Yak - dog food!"]
    assert w.hero.uhunger == 1000           # 900 + 100
    assert t.oeaten == 100
    assert w.occupation is not None
    ev = run_occupation(w, SeqRng())
    assert texts(ev) == ["You finish eating the tripe ration."]
    assert w.hero.uhunger == 1100           # 900 + 200


def test_eat_melon_nutrition():
    w = make_world()
    m = add_food(w, make_food(O.MELON))
    eat_food(w, "player", m.id, SeqRng())
    assert w.hero.uhunger == 1000           # 900 + 100


def test_eat_food_choke_says_food():
    """C: choke() with the food -- "choke over your <foodword>", and
    foodword is the flat class word "food" for every FOOD_CLASS item
    (not the food's name)."""
    w = make_world()
    ap = add_food(w, make_food(O.APPLE))
    set_hunger(w, 1950, uhs=SATIATED)
    ev = eat_food(w, "player", ap.id, SeqRng(2))
    assert texts(ev) == ["This apple is delicious!",
                         "You choke over your food.", "You die...",
                         "💀 You are dead!"]
    assert not w.hero.alive


# ------------------------------------------------------------
# the spell-casting gate (C: spelleffects_check)
# ------------------------------------------------------------

def _book_world():
    w = make_world()
    w.hero.uen = 20
    w.hero.uenmax = 20
    book = Item(id="book_0", otype=ObjectType.BOOK,
                name="book of healing", otyp=O.SPE_HEALING.value,
                oclass=ObjClass.SPBOOK.value, charges=5,
                spell_type=SpellType.HEALING, container="player")
    w.items[book.id] = book
    w.hero.inventory.append(book)
    return w, book


def test_cast_too_hungry_refused():
    """C: `u.uhunger <= 10` -> the refusal, no time, no draw, no
    energy, no page (the SPE_DETECT_FOOD exception is irrelevant)."""
    w, book = _book_world()
    w.hero.uhunger = 10
    ev = cast_spell(w, "player", book.id, None, SeqRng())
    assert texts(ev) == ["You are too hungry to cast that spell."]
    assert book.charges == 5
    assert w.hero.uen == 20


def test_cast_at_11_hunger_is_allowed():
    w, book = _book_world()
    w.hero.uhunger = 11
    ev = cast_spell(w, "player", book.id, None, SeqRng(1))   # success
    assert texts(ev)[0] == "You cast healing."
    assert book.charges == 4
    assert w.hero.uen == 15
    assert w.hero.uhunger == 11


# ------------------------------------------------------------
# the step() wiring
# ------------------------------------------------------------

def test_step_wires_eat_command():
    """The tick runs before the action (the hero phase order), so the
    meal lands on 899, not 900."""
    w = make_world()
    ap = add_food(w, make_food(O.APPLE))
    ev = step(w, EatCommand(ap.id), SeqRng())
    assert w.hero.uhunger == 949
    assert ap not in w.hero.inventory
    assert w.items.get(ap.id) is None
    assert w.turn == 1
    assert any(isinstance(e, MessageEvent)
               and e.text == "This apple is delicious!" for e in ev)


def test_step_ticks_hunger_every_turn():
    """C: gethungry() from the main loop -- once per round, in the
    hero phase, zero draws for the bare hero (the seeded suite stays
    put)."""
    w = make_world()
    set_hunger(w, 900)
    step(w, EatCommand("nope"), SeqRng())
    assert w.hero.uhunger == 899
    assert w.hero.uhs == NOT_HUNGRY


def test_step_fainted_hero_starves_if_not_fed():
    """The faint deepens while fainted (the ticker runs under the
    gate): the CON 12 floor is -220 (the C strict <), the metabolism
    rolls all succeed (1), the faint rolls all fail (1)."""
    w = make_world()
    set_hunger(w, -219, uhs=FAINTED, fainted=100)
    # metabolism (1: decrement) + the faint roll (1: fail); -220 is
    # not < -220
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 1))
    assert w.hero.alive
    assert w.hero.uhunger == -220
    assert texts(ev) == []
    ev = step(w, MoveCommand(1, 0), SeqRng(1, 1))
    assert texts(ev) == ["You die from starvation.", "💀 You are dead!"]
    assert not w.hero.alive
    assert w.hero.uhs == STARVED


# ------------------------------------------------------------
# choke() directly (the C function with the food name)
# ------------------------------------------------------------

def test_choke_direct_survive_and_die():
    """C choke() with the food: the gate, the 1/20 survive roll
    (morehungry(1000) -- the meal's own nutrition is not part of
    choke()), the death."""
    w = make_world()
    set_hunger(w, 1950, uhs=SATIATED)
    ap = make_food(O.APPLE)
    ev = choke(w, "player", ap, SeqRng(1))
    assert texts(ev) == ["You stuff yourself and then vomit voluminously."]
    assert w.hero.uhunger == 950            # 1950 - 1000
    assert w.hero.uhs == NOT_HUNGRY
    w = make_world()
    set_hunger(w, 1950, uhs=SATIATED)
    ev = choke(w, "player", ap, SeqRng(13))
    assert texts(ev) == ["You choke over your food.", "You die...",
                         "💀 You are dead!"]
    assert not w.hero.alive
