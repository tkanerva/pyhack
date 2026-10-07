"""Scroll system: read_scroll() applies the scroll's effect and
returns events (C: doread() + seffects(), src/read.c).

Ported onto the committed systems; the five implemented effects and
their C provenance:

- SCR_BLANK_PAPER     seffect_blank_paper: "blank" feedback; the
                      scroll is NOT used up (C: doread skips useup)
- SCR_ENCHANT_WEAPON  seffect_enchant_weapon (src/read.c) + chwepon
                      (src/wield.c): the +1 / blessed-rnd / spe>=9
                      amount, the soft +/-5 evaporate limit, the glow
                      line, the positive-enchant uncurse, the
                      high-spe vibration clue
- SCR_ENCHANT_ARMOR   seffect_enchant_armor (src/read.c) + some_armor
                      (src/do_wear.c): the cloak/suit/shirt ->
                      helmet/gloves/boots/shield 3/4-swap pick, the
                      elven vibration/evaporate warning, the (4-s)/2
                      base power + elven/nonmagical/blessed bonuses,
                      the BUC transfer, the cap
- SCR_REMOVE_CURSE    seffect_remove_curse (the unconfused branch):
                      a cursed scroll only disintegrates; otherwise
                      every carried item (blessed scroll) or every
                      worn item (C: the wornmask condition) is
                      uncursed -- silently, as C's uncurse() does
- SCR_TELEPORTATION   seffect_teleportation -> scrolltele (src/
                      teleport.c), on the walkable floor-tile set
                      (rules.teleport_to_floor -- the same dungeon
                      tile check the demo's trap / monster placement
                      uses)

STUB: the remaining C seffect_* handlers -- destroy armor, confuse /
scare monster, create monster, taming, genocide, light, gold / food
detection, identify, magic mapping, amnesia, fire, earth, punishment,
charging, stinking cloud -- raise NotImplementedError when read (the
demo never carries them).  Each lands with the machinery it needs:
monster generation (create / taming / genocide), the identification
system (identify / magic mapping), the level system (fire / earth /
light / teleport variants), the ball & chain (punishment), ...

Simplifications (documented, not bugs):

- no blind / confused / hallucinating reader variants (the demo hero
  has no such status path); C's alternate-outcome branches (the
  confused armor/weapon erodeproof flip, the confused remove-curse
  blessorcurse, the cursed-teleport level teleport, ...) are dropped
- the blessed teleport's controlled destination (C: getpos) collapses
  to the plain random teleport -- the console UI has no prompt
  machinery mid-step
- no conduct / livelog / discovery bookkeeping (makeknown / exercise /
  trycall); demo items are fully known
- enchant weapon: the worm-tooth <-> crysknife transformation, the
  cursed tin-opener weld branch and the artifact / magicbane clues are
  dropped (none of them is in the demo)
- enchant armor: the dragon-scales -> scale-mail merge is dropped (no
  dragon scales in the demo); the elven test is by table name (the
  ported Object row carries no OC_ELVEN flag; every C elven armor is
  named "elven ...")
- remove curse: C's saddle case and the confused branch are dropped;
  the scroll hides itself from its own scan (C skips it when its
  quantity is 1)
- the `some_armor` / `chwepon` monster-facing C generality is kept
  (functions over `Monster`), so the mon.c port reuses them

Draw-order discipline: every rng draw is an inline randint (C rn2 /
rnd sites, commented), so SeqRng tests audit the C branches one for
one.  No draw happens for a scroll that produces no effect branch
(plain +1 enchants, remove curse, blank paper).
"""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .items import consume_item, wielded_of
from .objects import (W_ARMC, W_ARM, W_ARMF, W_ARMG, W_ARMH, W_ARMOR,
                      W_ACCESSORY, W_ARMS, W_ARMU, W_WEP, object_type)
from .rules import roll, teleport_to_floor
from .types import Item, Monster, ObjectType, ScrollType, World
from . import worn

# C: objclass.h -- the enchantment clamp
SPE_LIM = 99


def _find_scroll(world: World, monster_id: str, item_id: str) -> Optional[Item]:
    item = world.items.get(item_id)
    if item is None or item.otype != ObjectType.SCROLL or item.container != monster_id:
        return None
    return item


def _yname(mon: Monster, item: Item) -> str:
    """C Yname2 / Yobjnam2 phrasing: "your X" for the hero,
    "name's X" for a monster."""
    if mon.is_hero:
        return f"your {item.name}"
    return f"{mon.name}'s {item.name}"


def _cap_spe(item: Item) -> None:
    """C: cap_spe (src/read.c) -- enchantment clamped to +/-SPE_LIM."""
    if abs(item.spe) > SPE_LIM:
        item.spe = SPE_LIM if item.spe > 0 else -SPE_LIM


def _is_elven(item: Item) -> bool:
    """C: is_elven_armor / is_elven_weapon (obj.h: the OC_ELVEN bit).
    The ported Object row carries no OC_ELVEN flag, and every elven
    armor / weapon of the C table is named "elven ..."; the name test
    over the table row is the exact stand-in for the demo subset."""
    row = object_type(item.otyp)
    return row is not None and row.name.startswith("elven")


def some_armor(world: World, mon: Monster, rng) -> Optional[Item]:
    """C: some_armor (src/do_wear.c) -- the armor an enchant-armor
    scroll targets: the cloak, else the suit, else the shirt; a worn
    helmet, gloves, boots or shield then takes over 3/4 of the time,
    in that order (each C `!rn2(4)` is a 3/4 draw).  None when the
    actor wears no armor at all.

    Draw note: a slot only draws when an earlier slot was already
    selected (C `!otmph` short-circuits) -- the draw order is the
    C order, auditable with SeqRng.
    """
    otmph = (worn.which_armor(world, mon, W_ARMC)
             or worn.which_armor(world, mon, W_ARM)
             or worn.which_armor(world, mon, W_ARMU))
    for mask in (W_ARMH, W_ARMG, W_ARMF, W_ARMS):
        otmp = worn.which_armor(world, mon, mask)
        if otmp and (otmph is None or rng.randint(1, 4) > 1):
            # C: !rn2(4) -- 3/4 chance the new slot takes over
            otmph = otmp
    return otmph


def _destroy_wielded(world: World, mon: Monster, weapon: Item) -> None:
    """C: useupall(uwep) -- the weapon disappears; the wielded slot
    (C: uwep) empties with it."""
    consume_item(world, mon.id, weapon.id)
    if mon.wielded == weapon.id:
        mon.wielded = None


# ------------------------------------------------------------
# The seffect_* handlers (C: the seffects() switch, src/read.c)
# ------------------------------------------------------------

def _seffect_blank_paper(world: World, actor: Monster) -> List[Event]:
    """C: seffect_blank_paper: "This scroll seems to be blank."  The
    scroll is NOT consumed (C: doread skips useup for
    SCR_BLANK_PAPER) -- the caller handles that split."""
    return [MessageEvent("This scroll seems to be blank.")]


def _seffect_enchant_weapon(world: World, mon: Monster, scroll: Item,
                            rng) -> List[Event]:
    """C: seffect_enchant_weapon (src/read.c) + chwepon (src/wield.c).

    The amount `s` of enchantment (C's formula, verbatim): -1 for a
    cursed scroll; with a weapon, 0-or-1 (`rn2(spe) == 0`) once the
    weapon is at spe >= 9, `rnd(3 - spe/3)` for a blessed scroll
    (C's truncating division), and the flat 1 otherwise.  chwepon
    applies it: the soft +5/-5 limit can evaporate the weapon (2/3 of
    the time when the sign pushes past it), the glow line, spe += s
    (the cap is the caller's _cap_spe), a positive enchantment
    uncurses, and the high-spe vibration clue.
    """
    weapon = wielded_of(world, mon.id)
    if weapon is None:
        # C: chwepon -> strange_feeling("Your hands twitch." /
        # "itch.") + useup
        return [MessageEvent("Your hands twitch." if scroll.cursed
                             else "Your hands itch.")]

    if scroll.cursed:
        s = -1
    elif weapon.spe >= 9:
        # C: (rn2(uwep->spe) == 0) -- usually 0, maybe 1
        s = 1 if rng.randint(1, weapon.spe) > 1 else 0
    elif scroll.blessed:
        # C: rnd(3 - uwep->spe / 3); int() truncates toward zero, as
        # C's integer division does
        s = roll(rng, 3 - int(weapon.spe / 3))
    else:
        s = 1

    events = _chwepon(world, mon, weapon, s, rng)
    _cap_spe(weapon)
    return events


def _chwepon(world: World, mon: Monster, weapon: Item, s: int,
             rng) -> List[Event]:
    """C: chwepon (src/wield.c), the scroll subset (the no-weapon
    branch is handled by the caller, as in C's structure)."""
    # C: the soft limit -- a weapon pushed past +5 (or under -5) by
    # the sign of the enchantment evaporates, 2/3 of the time
    if ((weapon.spe > 5 and s >= 0) or (weapon.spe < -5 and s < 0)) \
            and rng.randint(1, 3) > 1:
        # C: rn2(3) != 0 -> useupall(uwep)
        name = _yname(mon, weapon)
        _destroy_wielded(world, mon, weapon)
        return [MessageEvent(f"{name} violently glows for a while "
                             f"and then evaporates.")]

    # C: the glow line (xtime: |s| == 1 -> "moment", else "while";
    # s == 0 -> "violently glow")
    xtime = "moment" if s * s == 1 else "while"
    verb = "violently glows" if s == 0 else "glows"
    name = _yname(mon, weapon)
    events = [MessageEvent(f"{name} {verb} for a {xtime}.")]

    weapon.spe += s
    if s > 0 and weapon.cursed:
        weapon.cursed = False  # C: chwepon uncurses on a positive enchant

    # C: the elven / high-spe vibration clue (elven short-circuits the
    # draw, as C's is_elven_weapon test does)
    if weapon.spe > 5 and (_is_elven(weapon)
                           or rng.randint(1, 7) > 1):
        # C: !rn2(7) -- 1/7 for the non-elven case
        events.append(MessageEvent(f"{name} suddenly vibrates "
                                   f"unexpectedly."))
    return events


def _seffect_enchant_armor(world: World, mon: Monster, scroll: Item,
                           rng) -> List[Event]:
    """C: seffect_enchant_armor (src/read.c) + some_armor (src/
    do_wear.c), the non-confused subset."""
    armor = some_armor(world, mon, rng)
    if armor is None:
        # C: strange_feeling("Your skin glows then fades.") + useup
        return [MessageEvent("Your skin glows then fades.")]

    row = object_type(armor.otyp)
    elven = _is_elven(armor)
    sblessed, scursed = scroll.blessed, scroll.cursed

    # C: elven armor vibrates warningly when enchanted beyond a limit
    # (elven 5, else 3) -- checked against the raw spe, signed by the
    # scroll, and it evaporates when the roll says so (C: rn2(s) != 0)
    s = -armor.spe if scursed else armor.spe
    if s > (5 if elven else 3) and rng.randint(1, s) > 1:
        name = _yname(mon, armor)
        worn.setnotworn(mon, armor)  # C: remove_worn_item
        consume_item(world, mon.id, armor.id)  # C: useup(otmp)
        return [MessageEvent(f"{name} violently glows for a while, "
                             f"then evaporates.")]

    # C: the base power -- 2 for spe -1..+0, 1 for +1..+2, 0 for
    # +3..+4, ...; C's (4 - s) / 2 is a truncating division
    s = int((4 - s) / 2)
    # C: elven / nonmagical armor is easier to enchant; blessed
    # scrolls are more effective
    if elven:
        s += 1
    if not row.magic:
        s += 1
    if sblessed:
        s += 1
    if s <= 0:
        s = 0
        if armor.spe > 0 and rng.randint(1, armor.spe) > 1:
            # C: !rn2(otmp->spe) -- the rare +1 (draw only when spe > 0)
            s = 1
    else:
        s = roll(rng, s)
    if s > 11:
        s = 11  # C: "unlikely but possible: avoids an overflow later"
    if scursed:
        s = -s

    # C: the glow line, then the BUC transfer, then spe += s
    xtime = "moment" if s * s == 1 else "while"
    verb = "violently glows" if s == 0 else "glows"
    name = _yname(mon, armor)
    events = [MessageEvent(f"{name} {verb} for a {xtime}.")]
    if scursed and not armor.cursed:
        armor.cursed = True      # C: curse(otmp)
    elif sblessed and not armor.blessed:
        armor.blessed = True     # C: bless(otmp)
    elif not scursed and armor.cursed:
        armor.cursed = False     # C: uncurse(otmp)
    armor.spe += s
    _cap_spe(armor)

    # C: the trailing "suddenly vibrate unexpectedly." clue (elven
    # short-circuits the draw, as C does)
    if armor.spe > (5 if elven else 3) \
            and (elven or rng.randint(1, 7) > 1):
        events.append(MessageEvent(f"{name} suddenly vibrates "
                                   f"unexpectedly."))
    return events


def _seffect_remove_curse(world: World, mon: Monster, scroll: Item) -> List[Event]:
    """C: seffect_remove_curse (src/read.c), the unconfused branch:
    "You feel like someone is helping you."; a cursed scroll then
    only disintegrates; otherwise every carried item (blessed scroll)
    or every worn item (C: the wornmask condition) is uncursed --
    silently, as C's uncurse() (src/mkobj.c) does.  The scroll hides
    itself from its own scan (C skips it when its quantity is 1)."""
    events = [MessageEvent(
        "You feel like someone is helping you." if mon.is_hero
        else f"{mon.name} feels like someone is helping.")]
    if scroll.cursed:
        events.append(MessageEvent("The scroll disintegrates."))
        return events
    for item in mon.inventory:
        if item is scroll:
            continue
        # C: wornmask = owornmask & ~(W_BALL | W_ART | W_ARTI) -- the
        # demo's worn bits are the armor / accessory / weapon slots
        wornmask = item.owornmask & (W_ARMOR | W_ACCESSORY | W_WEP)
        if not (scroll.blessed or wornmask) or not item.cursed:
            continue
        item.cursed = False
    return events


def _seffect_teleportation(world: World, mon: Monster, rng) -> List[Event]:
    """C: seffect_teleportation (src/read.c) -> scrolltele (src/
    teleport.c).  The demo is single-level: the cursed / confused
    "level teleport" and the blessed scroll's controlled (getpos)
    destination both collapse to the plain random teleport on the
    walkable floor-tile set (rules.teleport_to_floor -- the same
    dungeon tile check the demo's trap / monster placement uses)."""
    return teleport_to_floor(world, mon.id, rng)


# ------------------------------------------------------------
# The command entry point (C: doread)
# ------------------------------------------------------------

def read_scroll(world: World, monster_id: str, item_id: str,
                rng) -> List[Event]:
    """C: doread (src/read.c): read a scroll and apply its effect.

    The scroll is consumed except SCR_BLANK_PAPER (C: doread skips
    useup for it).  Returns the events (the "you read the scroll"
    line, the effect's message lines, and any status / teleport
    events the effect produces).
    """
    item = _find_scroll(world, monster_id, item_id)
    if item is None:
        return [MessageEvent("You don't have such a scroll.")]
    st = item.scroll_type
    if st is None:
        return [MessageEvent("You have nothing to read.")]

    actor = world.actors[monster_id]
    if st is ScrollType.BLANK_PAPER:
        # C: no "you read the scroll" line, no useup
        return _seffect_blank_paper(world, actor)

    # C: the "you read the scroll" line, suppressed (nodisappear) for
    # the effects that describe the scroll's fate -- a cursed remove
    # curse in the subset
    nodisappear = st is ScrollType.REMOVE_CURSE and item.cursed
    events: List[Event] = [MessageEvent(
        "You read the scroll." if nodisappear
        else "As you read the scroll, it disappears.")]
    if st is ScrollType.ENCHANT_WEAPON:
        events += _seffect_enchant_weapon(world, actor, item, rng)
    elif st is ScrollType.ENCHANT_ARMOR:
        events += _seffect_enchant_armor(world, actor, item, rng)
    elif st is ScrollType.REMOVE_CURSE:
        events += _seffect_remove_curse(world, actor, item)
    elif st is ScrollType.TELEPORTATION:
        events += _seffect_teleportation(world, actor, rng)
    else:
        # STUB: the C seffect_<name> port (see the module docstring)
        raise NotImplementedError(
            f"the scroll of {st.name.lower().replace('_', ' ')} is not "
            f"ported yet (C: src/read.c seffects())")
    consume_item(world, monster_id, item.id)
    return events
