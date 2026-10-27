"""Hunger system: the per-turn gauge ticker, the state machine, and
eating (port of the hero-facing subset of src/eat.c, NetHack 5.0).

Ported onto the committed systems; the C provenance per function:

- init_uhunger   eat.c: the gauge to 900 / NOT_HUNGRY (hero init,
                 life-saving, the prayer results)
- tick_hunger    eat.c gethungry(): called once per round from the
                 main loop (src/allmain.c).  The main `uhunger--`
                 (with the fainted `!rn2(10)` slowdown -- C `Unaware`
                 is fainted/unconscious), then the 5.0 randomized
                 `accessorytime = rn2(20)` and its branches: odd ->
                 regeneration / encumbrance, even -> the Hunger /
                 Conflict properties + the even cases 0/4/8/12/16
                 (armor slow-digestion / left ring / worn amulet /
                 right ring / carried real Amulet), then newuhs(TRUE)
- newuhs         eat.c newuhs(incr): the state thresholds (>1000
                 SATIATED, >150 NOT_HUNGRY, >50 HUNGRY, >0 WEAK,
                 else FAINTING), the faint (the `rn2(20 - div) >= 19`
                 roll with `div = sgn(h) * ((abs(h)+5)/10)` --
                 NEGATIVE for h < 0, so the deeper the deficit the
                 WIDER the roll and the LONGER the `10 - div` faint),
                 the starvation death (`h < -(100 + 10*CON)`), the
                 HUNGRY / WEAK messages (the <145 / <45 splits, the
                 incr vs. not), and the "hunger and exhaustion" guard
- eat_food       eat.c doeat() subset: the carried-food find, the
                 is_edible refusal ("You cannot eat that!"), the
                 worn refusal, the fprefx first-bite messages, the
                 meal (the C multi-turn occupation, see below), the
                 first bite (C: start_eating's immediate bite), the
                 useup when the piece is gone
- _meal          eat.c eatfood() (the occupation fn) as a generator
                 (PLAN-OCCUPATION.md): one bite per round (the C
                 bite() -> lesshungry / consume_oeaten), the piece
                 consumed when it is gone (C: done_eating's useup +
                 the "You finish eating ..." line), the choke end
                 (C: bite() returning 1), the stolen-food abort (C:
                 the do_reset_eat branch), the interrupted-meal
                 cleanup (C: reset_eat -- the piece keeps its
                 oeaten bookkeeping for the resume)
- lesshungry / morehungry  eat.c: the gauge up / down with the >=1500
                 fullwarning line and the >=2000 choke
- choke          eat.c choke(): the SATIATED-only gate, the
                 `!rn2(20)` survive roll (1/20: "stuff yourself and
                 then vomit voluminously." + morehungry(1000)) vs.
                 the death (19/20: "choke over your food.")
- HU_STAT        eat.c hu_stat[]: the bottom-line texts (C botl.c
                 prints them when uhs != NOT_HUNGRY)

STUB: none -- the unported pieces are the documented
simplifications below (they are branches of the C code the demo
cannot reach, not separate handlers).

Simplifications (documented, not bugs):

- The multi-turn meal IS the C occupation, now as a generator
  (PLAN-OCCUPATION.md): the one-turn house rule of PLAN-HUNGER.md
  decision 5 is superseded -- reqtime (the table's oc_delay, scaled
  by the remaining piece), nmod (the nutrition per bite), the first
  bite on the command turn (C: start_eating), one bite per round
  (C: eatfood + bite), the interrupted-meal resume with reduced
  duration (C: the already_partly_eaten path), the choke end (the
  meal dies with a survived choke, the piece stays).  Still out: the
  tins (opentin), the corpse / glob specifics, the weight bookkeeping
  (recalc_wt), the "resume your meal" do-again prompt
- no polymorphic edibility (the fire-elemental / metallivorous /
  ghoul / gelatinous-cube is_edible branches): the demo hero is a
  fixed human -- edibility is the FOOD_CLASS test
- no corpse / egg specifics (rotting, poisoning, stoning, cpostfx
  intrinsics, the egg's corpsenm): the demo floor carries plain
  fruit / rations; the fprefx subset is the FOOD_RATION and
  TRIPE_RATION cases + the give_feedback default (the ration
  "bland." line included)
- the ATEMP(A_STR) weak penalty is dropped (no ability base/temp
  split yet, PLAN-HUNGER.md 5.1); the WEAK state is tracked and
  messaged
- no EProtection extrinsics in the ring cases (the +0-ring-of-
  protection "only source" clause is dropped; the ported test is
  `spe != 0 or not oc_charged`), no encumbrance (the odd-branch
  near_capacity decrement), no deafness (the faint's HDeaf half),
  no debug_hunger option, no conduct / livelog / exercise
- vomit() is the message only (no nomul -2, no acid breath, no
  altar wrath); the tripe ration's +1 XP and 1/2 vomiting are
  dropped (no XP / vomiting system)
- the "too hungry to cast that spell" gate (C spelleffects_check)
  lives in core.spells.cast_spell -- one line, next to the Pw check

Draw-order discipline (PLAN-HUNGER.md decision 4, the one
documented deviation from C): C 5.0 draws `accessorytime = rn2(20)`
UNCONDITIONALLY per round; this port draws it only when at least
one accessory branch can burn (a worn ring / amulet, a carried real
Amulet, or the regeneration / Hunger / Conflict / slow-digestion
properties).  The bare demo hero is therefore a ZERO-DRAW path --
the same house rule that kept AC_VALUE and the scroll port from
touching the seeded suite -- and the C draw order resumes the moment
the hero wears the +1 ring of protection.  Same for the fainted
metabolism roll (only while fainted) and the faint roll (only in
the FAINTING branch).
"""
from __future__ import annotations

from typing import Generator, List, Optional

from .events import Event, MessageEvent
from .hacklib import rounddiv, sgn
from .items import consume_item
from .occupation import OccupationStopped, start_occupation
from .objects import (O, ObjClass, Prop, W_AMUL, W_ARMOR, W_RINGL, W_RINGR,
                      W_TOOL, object_type)
from .rules import apply_damage, current_ability
from .types import (DamageType, HungerState, Item, Monster, World)
from .worn import which_armor

# C: the hard-coded gauge thresholds of eat.c
HUNGER_CAP = 2000    # `u.uhunger >= 2000` -- the choke
FULL_WARN = 1500     # `u.uhunger >= 1500` -- the fullwarning line
HUNGER_START = 900   # init_uhunger()

# C: the hu_stat[] array (eat.c) -- the bottom-line texts, indexed
# by the HungerState (C botl.c prints them when uhs != NOT_HUNGRY)
HU_STAT = ("Satiated", "        ", "Hungry  ", "Weak    ",
           "Fainting", "Fainted ", "Starved ")


def init_uhunger(world: World, actor_id: str) -> None:
    """C: init_uhunger() (src/eat.c) -- the gauge to 900 / NOT_HUNGRY
    (hero init, life-saving, the prayer results)."""
    mon = world.actors[actor_id]
    mon.uhunger = HUNGER_START
    mon.uhs = HungerState.NOT_HUNGRY


# ------------------------------------------------------------
# The state machine (eat.c newuhs)
# ------------------------------------------------------------

def hunger_state(h: int) -> HungerState:
    """C: the `newhs` threshold step of newuhs()."""
    if h > 1000:
        return HungerState.SATIATED
    if h > 150:
        return HungerState.NOT_HUNGRY
    if h > 50:
        return HungerState.HUNGRY
    if h > 0:
        return HungerState.WEAK
    return HungerState.FAINTING


def newuhs(world: World, actor_id: str, incr: bool, rng) -> List[Event]:
    """C: newuhs(incr) (src/eat.c) -- compute and comment on the
    (new?) hunger status.  `incr` is True when the gauge just DROPPED
    (the ticker / morehungry) and False when it ROSE (lesshungry);
    C phrases the HUNGRY / WEAK messages differently for the two
    directions."""
    mon = world.actors[actor_id]
    h = mon.uhunger
    events: List[Event] = []
    newhs = hunger_state(h)

    if newhs == HungerState.FAINTING:
        # C: sgn(u.uhunger) * ((abs(u.uhunger) + 5) / 10) -- for h < 0
        # this is NEGATIVE, so 20 - div WIDENS the faint roll and
        # 10 - div LENGTHENS the faint (the deeper the deficit)
        div = sgn(h) * ((abs(h) + 5) // 10)
        if mon.fainted > 0:
            # C: is_fainted()
            newhs = HungerState.FAINTED
        if (int(mon.uhs) <= int(HungerState.WEAK)
                # C: rn2(20 - div) >= 19 -- the C value is 0-based, so
                # the 1-based draw fires on its TOP value (1/20 at div 0)
                or rng.randint(1, 20 - div) >= 20):
            if mon.fainted == 0:
                # C: !is_fainted() && gm.multi >= 0
                mon.fainted = 10 - div
                events.append(MessageEvent("You faint from lack of food."))
                newhs = HungerState.FAINTED
            # C: the HDeaf increment + nomul -- no deafness, the
            # fainted counter IS the multi (PLAN-HUNGER.md 4)
        elif h < -(100 + 10 * current_ability(mon, "con")):
            # C: ACURR(A_CON); done(STARVING), killer "starvation"
            mon.uhs = HungerState.STARVED
            events.append(MessageEvent("You die from starvation."))
            events += apply_damage(world, actor_id, mon.hp,
                                   DamageType.STARVING, "starvation",
                                   message=False)
            return events

    if newhs != mon.uhs:
        # C: ATEMP(A_STR) = -1 entering WEAK / 0 leaving it -- no
        # ability base/temp split in pyhack yet (PLAN-HUNGER.md 5.1);
        # the state change is tracked and messaged, the STR effect
        # deferred
        if newhs == HungerState.HUNGRY:
            if not incr:
                text = "You only feel hungry now."
            elif h < 145:
                text = "You feel hungry."
            else:
                text = "You are beginning to feel hungry."
            events.append(MessageEvent(text))
        elif newhs == HungerState.WEAK:
            if not incr:
                text = "You are still weak."
            elif h < 45:
                text = "You feel weak."
            else:
                text = "You are beginning to feel weak."
            events.append(MessageEvent(text))
        mon.uhs = newhs
        # C: `if ((Upolyd ? u.mh : u.uhp) < 1)` -- "hunger and
        # exhaustion" (killer "exhaustion"); unreachable in pyhack
        # (apply_damage already kills at hp 0), kept for fidelity
        if mon.alive and mon.hp < 1:
            mon.uhs = HungerState.STARVED
            events.append(MessageEvent("You die from hunger and exhaustion."))
            events += apply_damage(world, actor_id, mon.hp,
                                   DamageType.STARVING, "exhaustion",
                                   message=False)
    return events


# ------------------------------------------------------------
# The per-round ticker (eat.c gethungry)
# ------------------------------------------------------------

def _accessory_can_burn(world: World, mon: Monster) -> bool:
    """Whether at least one `accessorytime` branch of C gethungry can
    burn nutrition for this actor (PLAN-HUNGER.md decision 4): the
    rn2(20) draw is made only in that case, so the bare hero is a
    zero-draw path (C draws unconditionally; the draw changes state
    only when a branch can burn)."""
    if (Prop.REGENERATION in mon.intrinsics
            or Prop.HUNGER in mon.intrinsics
            or Prop.CONFLICT in mon.intrinsics
            or Prop.SLOW_DIGESTION in mon.intrinsics):
        return True
    for mask in (W_RINGL, W_RINGR, W_AMUL):
        if which_armor(world, mon, mask) is not None:
            return True
    # C case 16: u.uhave.amulet (carrying the real Amulet)
    return any(it.otyp == O.AMULET_OF_YENDOR for it in mon.inventory)


def _ring_burns(ring: Optional[Item]) -> bool:
    """C: the `uleft` / `uright` condition of gethungry's cases 4/12:
    not a meat ring, and (spe != 0, or the type is not `oc_charged`,
    or the +0-ring-of-protection special case -- the last clause reads
    the extrinsic `EProtection`, unported (PLAN-HUNGER.md 4), so it
    is dropped)."""
    if ring is None or ring.otyp == O.MEAT_RING:
        return False
    row = object_type(ring.otyp)
    return ring.spe != 0 or not row.charged


def tick_hunger(world: World, actor_id: str, rng) -> List[Event]:
    """C: gethungry() (src/eat.c) -- called once per round from the
    main loop (src/allmain.c), including while the hero is fainted /
    asleep (that is how a faint deepens into starvation).  Wire:
    core.step, after the ring tick."""
    mon = world.actors[actor_id]
    if not mon.alive:
        return []
    # C: the main decrement -- the demo hero is a fixed human
    # (carnivorous, never Slow_digestion), so it always applies except
    # for the fainted slowdown:
    #   `(!Unaware || !rn2(10))` -- Unaware is fainted / unconscious
    if mon.fainted > 0:
        # C: !rn2(10) -- the 0-based draw is zero 1 in 10, the slow
        # metabolism (the 1-based draw fires on its BOTTOM value)
        if rng.randint(1, 10) == 1:
            mon.uhunger -= 1
    else:
        mon.uhunger -= 1               # C: ordinary food consumption

    if _accessory_can_burn(world, mon):
        # C: accessorytime = rn2(20) -- 0..19, the 1-based draw
        # shifted back down (case 0 is the slow-digestion armor turn)
        accessorytime = rng.randint(1, 20) - 1
        left = which_armor(world, mon, W_RINGL)
        right = which_armor(world, mon, W_RINGR)
        if accessorytime % 2:   # odd
            if Prop.REGENERATION in mon.intrinsics:
                # C: (HRegeneration & ~FROMFORM) || (ERegeneration & ~...)
                mon.uhunger -= 1
            # C: near_capacity() > SLT_ENCUMBER -- no encumbrance
            # system (PLAN-HUNGER.md 5.3)
        else:   # even
            if Prop.HUNGER in mon.intrinsics:
                mon.uhunger -= 1       # C: Hunger
            if Prop.CONFLICT in mon.intrinsics:
                mon.uhunger -= 1       # C: HConflict || (EConflict & ~W_ARTI)
            if accessorytime == 0:
                # C: the armor slow-digestion burns nutrition (it is
                # not a ring, so the ring turns do not cover it)
                if (Prop.SLOW_DIGESTION in mon.intrinsics
                        and (left is None
                             or left.otyp != O.RIN_SLOW_DIGESTION)
                        and (right is None
                             or right.otyp != O.RIN_SLOW_DIGESTION)):
                    mon.uhunger -= 1
            elif accessorytime == 4:
                if _ring_burns(left):
                    mon.uhunger -= 1
            elif accessorytime == 8:
                amul = which_armor(world, mon, W_AMUL)
                if amul is not None and amul.otyp != O.FAKE_AMULET_OF_YENDOR:
                    mon.uhunger -= 1
            elif accessorytime == 12:
                if _ring_burns(right):
                    mon.uhunger -= 1
            elif accessorytime == 16:
                if any(it.otyp == O.AMULET_OF_YENDOR
                       for it in mon.inventory):
                    mon.uhunger -= 1

    return newuhs(world, actor_id, True, rng)


# ------------------------------------------------------------
# The gauge up / down (eat.c lesshungry / morehungry)
# ------------------------------------------------------------

def choke(world: World, actor_id: str, item: Optional[Item],
          rng) -> List[Event]:
    """C: choke() (src/eat.c) -- only reaches the real branch when the
    pre-meal state was SATIATED (C `u.uhs != SATIATED` early-return;
    the amulet-of-strangulation path is unported).  Survive 1/20
    (`!rn2(20)`): vomit + morehungry(1000); else (19/20) the choking
    death -- choking is in C nearly always fatal.  `item` is the food
    being choked on (C: foodword = "food" for FOOD_CLASS items)."""
    mon = world.actors[actor_id]
    if mon.uhs != HungerState.SATIATED:
        return []
    events: List[Event] = []
    if rng.randint(1, 20) == 1:   # C: !rn2(20) -- survives 1 in 20
        events.append(MessageEvent(
            "You stuff yourself and then vomit voluminously."))
        # C: morehungry(Hunger ? (u.uhunger - 60) : 1000) -- the demo
        # hero has no dragon-skin Hunger property, so the flat 1000
        events += morehungry(world, actor_id, 1000, rng)
        # C: vomit() -- the nomul -2 / acid breath / altar wrath are
        # dropped (PLAN-HUNGER.md 4)
    else:
        what = "your food" if item is not None else "it"   # C: foodword(food) is the flat "food" for FOOD_CLASS
        events.append(MessageEvent(f"You choke over {what}."))
        events.append(MessageEvent("You die..."))
        # C: done(CHOKING), killer "Choked on ..."
        events += apply_damage(world, actor_id, mon.hp,
                               DamageType.STARVING, "choking",
                               message=False)
    return events


def lesshungry(world: World, actor_id: str, num: int, rng,
               item: Optional[Item] = None) -> List[Event]:
    """C: lesshungry() (src/eat.c) -- the gauge UP (after eating, and
    after drinking fruit juice): the >=1500 fullwarning line, the
    >=2000 choke, then newuhs(FALSE).  `item` is the food being eaten
    (C's bite() chokes with the victual piece; the non-meal choke is
    the bare choke(0) -> "You choke over it.")."""
    mon = world.actors[actor_id]
    events: List[Event] = []
    mon.uhunger += num
    if mon.uhunger >= HUNGER_CAP:
        events += choke(world, actor_id, item, rng)
    elif mon.uhunger >= FULL_WARN:
        if Prop.HUNGER not in mon.intrinsics:   # C: !Hunger
            events.append(MessageEvent(
                "You're having a hard time getting all of it down."))
    return events + newuhs(world, actor_id, False, rng)


def morehungry(world: World, actor_id: str, num: int,
               rng) -> List[Event]:
    """C: morehungry() (src/eat.c) -- the gauge DOWN (after vomiting,
    after feats of magic): newuhs(TRUE)."""
    mon = world.actors[actor_id]
    mon.uhunger -= num
    return newuhs(world, actor_id, True, rng)


# ------------------------------------------------------------
# Eating (eat.c doeat, the carried-food subset)
# ------------------------------------------------------------

def _find_food(world: World, actor_id: str, item_id: str) -> Optional[Item]:
    """The carried item (like _find_scroll / _find_potion).  C doeat
    also offers floor food (floorfood's prompt); the command names a
    carried item, house pattern."""
    item = world.items.get(item_id)
    if item is None or item.container != actor_id:
        return None
    return item


def _fprefx(mon: Monster, item: Item) -> List[Event]:
    """C: fprefx() first-bite messages (src/eat.c) -- the demo subset:
    the FOOD_RATION two-tier lines, the TRIPE_RATION "Yak - dog food!"
    (the +1 XP and the 1/2 vomiting are dropped: no XP / vomiting
    system), and the give_feedback default (the ration "bland." line
    included; the hallucinating variants dropped)."""
    if item.otyp == O.FOOD_RATION:
        # C: "200+800 remains below 1000+1, the satiation threshold";
        # "700-1+800 remains below 1500, the choking threshold"
        if mon.uhunger <= 200:
            return [MessageEvent("This food really hits the spot!")]
        if mon.uhunger < 700:
            return [MessageEvent("This satiates your stomach!")]
        return []
    if item.otyp == O.TRIPE_RATION:
        return [MessageEvent("Yak - dog food!")]
    # C: the give_feedback default -- "This %s is %s"
    if item.cursed:
        taste = "terrible!"
    elif item.otyp in (O.CRAM_RATION, O.K_RATION, O.C_RATION):
        taste = "bland."
    else:
        taste = "delicious!"
    return [MessageEvent(f"This {item.name} is {taste}")]


def _meal_plan(item: Item, resume: bool):
    """C: the doeat reqtime / nmod calculation (src/eat.c:3054-3081),
    the demo subset: the bite size is the remaining nutrition over
    the duration, and the duration is the table's oc_delay scaled by
    the remaining piece (the C rounddiv recompute of the
    already_partly_eaten path).  Returns (reqtime, nmod), or None
    when the piece is fully eaten (or the table row has no delay).
    """
    row = object_type(item.otyp)
    full = row.nutrition
    left = full - item.oeaten
    if left <= 0 or row.delay <= 0:
        return None
    if resume:
        # C: reqtime = rounddiv(oc_delay * oeaten_remaining, basenutrit)
        reqtime = max(1, rounddiv(row.delay * left, full))
    else:
        reqtime = row.delay
    # C: nmod = the nutrition per bite (the oeaten / reqtime split)
    nmod = max(1, rounddiv(left, reqtime))
    return reqtime, nmod


def _meal(world: World, actor_id: str, item_id: str,
          nmod: int) -> Generator[List[Event], None, List[Event]]:
    """C: eatfood() (src/eat.c:524-546) -- the eating occupation as a
    generator: one bite per round (the C bite() call), the piece
    consumed when it is gone (C: done_eating).  The state (the item,
    the bite size, the meal progress) is in this frame -- the C
    svc.context.victual struct.

    The FIRST bite was already eaten on the command turn (C:
    start_eating's immediate bite); the loop is the C eatfood() body:
    validate the piece (C: the "maybe it was stolen?" branch ->
    do_reset_eat), bite (C: bite() -> lesshungry + consume_oeaten),
    the choke end (C: bite() returning 1), and the completion
    (C: done_eating's useup + "You finish eating ...")."""
    mon = world.actors[actor_id]
    ev: List[Event] = []
    try:
        while True:
            rng = yield ev  # sent: this round's rng; yielded: events
            item = world.items.get(item_id)
            if item is None or item.container != actor_id:
                # C: the eaten piece is gone (stolen / used up) --
                # do_reset_eat: the meal ends, no message
                return []
            full = object_type(item.otyp).nutrition
            pre = mon.uhs
            pre_h = mon.uhunger
            ev += lesshungry(world, actor_id, nmod, rng, item=item)
            item.oeaten = min(item.oeaten + nmod, full)
            if not mon.alive:
                # the choke death (C: done(CHOKING)) -- the step's
                # _finish ends the game; the piece stays
                return ev
            if pre == HungerState.SATIATED and pre_h + nmod >= HUNGER_CAP:
                # the choke (death or the survived vomit): C's bite()
                # returns 1 and the meal ends -- the piece stays for
                # a later resume
                return ev
            if item.oeaten >= full:
                # done (C: done_eating): consume the piece
                consume_item(world, actor_id, item.id)
                return ev + [MessageEvent(
                    f"You finish eating the {item.name}.")]
    except OccupationStopped:
        # C: reset_eat() -- the piece stays carried with its oeaten
        # bookkeeping; the resume is an EatCommand on the same item
        return []


def eat_food(world: World, actor_id: str, item_id: str,
             rng) -> List[Event]:
    """C: doeat() (src/eat.c), the carried-food subset: find, the
    edibility refusals, the fprefx first-bite feedback, the meal.

    The meal is the C multi-turn occupation as a generator
    (PLAN-OCCUPATION.md): the first bite happens on THIS turn (C:
    start_eating's immediate bite), and when the piece is not done
    the remainder runs as world.occupation (one bite per round, the
    _meal generator).  A partially eaten piece is resumed with a
    reduced duration (C: the already_partly_eaten path).  The old
    one-turn house rule (PLAN-HUNGER.md decision 5) is superseded;
    the one-turn foods (the delay 1 apple / orange / melon) behave
    exactly as before."""
    item = _find_food(world, actor_id, item_id)
    if item is None:
        return [MessageEvent("You don't have such food.")]
    # C: is_edible() -- the demo hero is a fixed human, so the
    # FOOD_CLASS test (the polymorphic branches are dropped)
    if item.oclass != ObjClass.FOOD:
        return [MessageEvent("You cannot eat that!")]
    # C: doeat's worn refusal
    if item.owornmask & (W_ARMOR | W_TOOL | W_AMUL):
        return [MessageEvent("You can't eat something you're wearing.")]
    # C: unreachable (the input is queued while an occupation runs);
    # the direct-call guard (step() never dispatches two commands)
    if world.occupation is not None:
        return [MessageEvent("You are already busy.")]
    resume = item.oeaten > 0
    plan = _meal_plan(item, resume)
    if plan is None:
        # the piece is fully eaten (a stale item) -- C: the doeat
        # used-up branch (the zero_victual reset)
        consume_item(world, actor_id, item.id)
        return []
    reqtime, nmod = plan
    mon = world.actors[actor_id]
    full = object_type(item.otyp).nutrition
    events: List[Event] = []
    if resume:
        # C: You("%s %s.", (reqtime == 1) ? "eat" : "begin eating",
        #     doname(otmp))
        verb = "eat" if reqtime == 1 else "begin eating"
        events.append(MessageEvent(f"You {verb} the {item.name}."))
    else:
        events += _fprefx(mon, item)
    # the first bite (C: the start_eating bite) -- the meal chokes
    # with its food (C: bite() -> choke(piece))
    pre = mon.uhs
    pre_h = mon.uhunger
    events += lesshungry(world, actor_id, nmod, rng, item=item)
    item.oeaten = min(item.oeaten + nmod, full)
    if item.oeaten >= full:
        # a one-bite piece (C: the reqtime 1 path -- no finish line;
        # the fprefx was the whole feedback)
        consume_item(world, actor_id, item.id)
        return events
    if not mon.alive:
        return events  # the choke death -- the step ends the game
    if pre == HungerState.SATIATED and pre_h + nmod >= HUNGER_CAP:
        return events  # the choke vomit -- the meal ends, the piece stays
    # the remainder of the meal (C: set_occupation(eatfood, "eating %s",
    # food_xname(otmp, TRUE)) -- the xname carries the "the")
    start_occupation(world, _meal(world, actor_id, item.id, nmod),
                     f"eating the {item.name}")
    return events
