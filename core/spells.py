"""Spell system: cast_spell() -- the caster half of the zap port.

C sources: src/spell.c (`spelleffects()` / `spelleffects_check()` --
the hero cast pipeline) + the shared machinery in core/zap.py (see
there for the C provenance of the whole design).

In C, spelleffects() builds a temporary pseudo spellbook object
(mksobj(spellid), quan 20 so useup() leaves it alone) and hands it to
the SAME weffects() the wands use.  pyhack replaces the pseudo object
with a `ZapSpec`: the caster-side differences -- the Pw cost
(SPELL_LEV_PW), the failure roll (`rnd(100) > percent_success`), the
spell power (`u.ulevel / 2 + 1` dice) and the spell damage bonus
(spell_damage_bonus, the INT/level bonus) -- are computed HERE and
carried as VALUES in the spec; the effect code itself lives in
core.zap.ZAP_EFFECTS, which the wands call with their own specs.

C check order (spelleffects_check -> spelleffects), kept:

1. the energy check (`u.uen < SPELL_LEV_PW(lev)`) -- no time, no draw,
   no charge
2. the failure roll (`rnd(100) > percent_success`) -- a fizzle costs
   the turn but NOT the energy (C: the drain is in spelleffects, after
   the check) and no book page (3.x: the page is used up after a
   successful cast)
3. the cast: the "you cast" line, the effect, the energy drain, the
   page

Simplifications (documented, not bugs):

- percent_success is reduced to the demo: the INT base (C:
  11 * INT / 2) minus the unskilled-caster difficulty growth
  (C: (spellev - 1) * 4), clamped to a percentile -- C's role skill
  tables, encumbrance penalties and spell-specific machinery are
  dropped (the demo hero has no role skill state)
- spell_damage_bonus: the INT/level bonus of C zap.c
  spell_damage_bonus, with the INT <= 9 "never reduce below 1" floor
  dropped (unreachable: the demo hero's INT is fixed)
- the fireball is the demo's documented simplification (everything
  adjacent to the caster, C 5.0's explode() at a distant point has no
  demo equivalent); the C 5.0 cone-of-cold-as-explosion is kept in its
  C 3.x beam form ("a cold stream") so it shares the wand of cold's
  ZapEffect.COLD
- the book is the power source (C: the spellbook's pages): one charge
  per successful cast, consumed at 0
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .energy import drain_energy, spell_lev_pw
from .events import Event, MessageEvent
from .items import consume_item
from .rules import apply_damage, heal, roll
from .types import (DamageType, Direction, Item, Monster, ObjectType,
                    SpellType, ZapEffect, World)
from .zap import ZAP_EFFECTS, ZapSpec, zap

HEALING_POWER = 12  # the demo's flat healing (C: the healing spell's rnd)

# C: the spell levels of the objects table (core/objects_data.py, the
# SPELL(name, descr, skill, prob, delay, LEVEL, ...) rows).  The Pw
# cost is level * 5 (energy.spell_lev_pw, C SPELL_LEV_PW).
# TELEPORT is the 3.x self-teleport level (the 5.0 row is the
# targeted SPE_TELEPORT_AWAY); LIGHTNING has no 5.0 row (3.x level).
SPELL_LEVELS: Dict[SpellType, int] = {
    SpellType.MAGIC_MISSILE: 2,
    SpellType.FIREBALL: 4,
    SpellType.CONE_OF_COLD: 4,
    SpellType.LIGHTNING: 4,
    SpellType.SLEEP: 3,
    SpellType.DEATH: 7,
    SpellType.POLYMORPH: 6,
    SpellType.CANCELLATION: 7,
    SpellType.TELEPORT: 3,
    SpellType.HEALING: 1,
}

# C: the spelleffects() "these spells are all duplicates of wand
# effects" group -- the beam spells dispatch onto the SAME ZapEffect
# the wands use (the wand of cold and the cone of cold book are one
# effect, C ZT_COLD / "a cold stream"; the magic missile book runs the
# wand of magic missile's ZT_MAGIC_MISSILE, the striking wand's cousin)
SPELL_ZAPS: Dict[SpellType, ZapEffect] = {
    SpellType.MAGIC_MISSILE: ZapEffect.MAGIC,
    SpellType.CONE_OF_COLD: ZapEffect.COLD,
    SpellType.LIGHTNING: ZapEffect.LIGHTNING,
    SpellType.SLEEP: ZapEffect.SLEEP,
    SpellType.DEATH: ZapEffect.DEATH,
    SpellType.POLYMORPH: ZapEffect.POLYMORPH,
}

# C: the self-targeted spell effects (the spelleffects atme /
# zapyourself paths): the same registry functions, invoked without a
# beam -- the caster is the target (the cancellation spell cancels
# YOUR items, the teleport spell moves YOU)
SELF_ZAPS: Dict[SpellType, ZapEffect] = {
    SpellType.TELEPORT: ZapEffect.TELEPORT,
    SpellType.CANCELLATION: ZapEffect.CANCELLATION,
}


def _find_book(world: World, caster_id: str, book_id: str) -> Optional[Item]:
    item = world.items.get(book_id)
    if item is None or item.otype != ObjectType.BOOK or item.container != caster_id:
        return None
    return item


def spell_damage_bonus(caster: Monster) -> int:
    """C: spell_damage_bonus (src/zap.c) -- the INT/level damage bonus
    the SPELL side adds to its rolled damage (wands add nothing):

        INT <= 9               -3  (C floors the total at 1 -- the
                                    demo's fixed INT never hits it)
        INT <= 13, or level < 5   0
        INT <= 18               +1
        INT <= 24, or level < 14 +2
        above                   +3
    """
    i, lvl = caster.uint, caster.ulevel
    if i <= 9:
        return -3
    if i <= 13 or lvl < 5:
        return 0
    if i <= 18:
        return 1
    if i <= 24 or lvl < 14:
        return 2
    return 3


def spell_success_chance(caster: Monster, spell_level: int) -> int:
    """C: percent_success (src/spell.c) reduced to the demo: the INT
    base (C: 11 * INT / 2) minus the difficulty growth of an unskilled
    caster (C: (spellev - 1) * 4, the skill/level terms of C's
    difficulty formula at the demo's fixed values), clamped to a
    percentile.  C's role skill tables, the encumbrance penalties and
    the spell-specific machinery are dropped (the demo hero has no
    role skill state)."""
    chance = caster.uint * 11 // 2 - (spell_level - 1) * 4
    return max(0, min(100, chance))


def _fireball(world: World, caster: Monster, rng) -> List[Event]:
    """The demo's fireball (C: the SPE_FIREBALL explode reduced to the
    established simplification): everything adjacent to the caster
    takes 1d6 fire.  The dice are rolled per victim, in actor order."""
    events: List[Event] = []
    hit_anyone = False
    for m in world.actors.values():
        if m.is_hero or not m.alive or m.pos == caster.pos:
            continue
        if (abs(m.pos[0] - caster.pos[0]) <= 1
                and abs(m.pos[1] - caster.pos[1]) <= 1):
            dmg = roll(rng, 6)
            events += apply_damage(world, m.id, dmg, DamageType.FIRE,
                                   "spell:fireball")
            hit_anyone = True
    if not hit_anyone:
        events.append(MessageEvent("The fireball bursts harmlessly."))
    return events


def cast_spell(world: World, caster_id: str, book_id: str,
               direction: Optional[Direction], rng) -> List[Event]:
    """C: the spelleffects() pipeline (see the module docstring for
    the check order): find the book, check the Pw, roll the failure
    check, cast (the effect through the shared ZAP_EFFECTS registry,
    the wand's counterpart), drain the Pw, use a page."""
    book = _find_book(world, caster_id, book_id)
    if book is None:
        return [MessageEvent("You don't have such a book.")]
    if book.charges <= 0:
        return [MessageEvent("The book is blank.")]

    caster = world.actors[caster_id]
    st = book.spell_type or SpellType.MAGIC_MISSILE
    spell_name = st.name.lower().replace("_", " ")
    lev = SPELL_LEVELS.get(st, 1)
    cost = spell_lev_pw(lev)

    # 1. C: spelleffects_check -- `if (*energy > u.uen)` -- no time,
    # no draw, no charge
    if caster.uen < cost:
        return [MessageEvent("You don't have enough energy to cast that!"
                             if caster.is_hero
                             else f"{caster.name} doesn't have enough energy!")]

    # 2. C: the failure roll -- `rnd(100) > percent_success(spell)` --
    # a fizzle costs the turn, NOT the energy (the drain in C is in
    # spelleffects, after the check) and no book page
    chance = spell_success_chance(caster, lev)
    if rng.randint(1, 100) > chance:
        return [MessageEvent("You fail to cast the spell correctly."
                             if caster.is_hero
                             else f"{caster.name} fails to cast the spell correctly.")]

    # 3. the cast
    events: List[Event] = [MessageEvent(
        f"You cast {spell_name}." if caster.is_hero
        else f"{caster.name} casts {spell_name}.")]

    if st == SpellType.FIREBALL:
        # area effect (C: the SPE_FIREBALL explode; no direction --
        # the demo's adjacent burst ignores it)
        events += _fireball(world, caster, rng)
    elif st in SPELL_ZAPS:
        # the beam spells (C: ubuzz(BZ_U_SPELL(...), u.ulevel / 2 + 1)):
        # the power is the caster's level / 2 + 1 dice, the damage
        # bonus the INT/level spell_damage_bonus -- both computed
        # HERE (the caster side), carried in the spec, applied by the
        # shared effect the wands use too
        effect = SPELL_ZAPS[st]
        spec = ZapSpec(effect=effect,
                       power=caster.ulevel // 2 + 1,
                       damage_bonus=spell_damage_bonus(caster),
                       source=book)
        if direction is None:
            # C: the zapyourself path -- a directional spell cast
            # without a direction hits the caster
            spec = ZapSpec(effect=effect,
                           power=caster.ulevel // 2 + 1,
                           damage_bonus=spell_damage_bonus(caster),
                           source=book, noun="spell")
            events += ZAP_EFFECTS[effect](world, caster, caster, spec, rng)
        else:
            noun = ("ray" if st in (SpellType.SLEEP, SpellType.POLYMORPH)
                    else "spell")
            spec = ZapSpec(effect=effect,
                           power=caster.ulevel // 2 + 1,
                           damage_bonus=spell_damage_bonus(caster),
                           source=book, noun=noun)
            events += zap(world, caster_id, direction, spec, rng)
    elif st in SELF_ZAPS:
        # C: the atme path -- the self effects invoke the shared
        # registry functions directly, the caster as the target
        effect = SELF_ZAPS[st]
        spec = ZapSpec(effect=effect, source=book)
        events += ZAP_EFFECTS[effect](world, caster, caster, spec, rng)
    elif st == SpellType.HEALING:
        # C: the SPE_HEALING potion-effect family (no wand counterpart:
        # caster-side only)
        events += heal(world, caster_id, HEALING_POWER)
    else:
        events.append(MessageEvent(f"The {spell_name} spell does nothing."))

    # the energy drain + the page (C: after the effect)
    drain_energy(world, caster_id, cost)
    book.charges -= 1
    if book.charges <= 0:
        consume_item(world, caster_id, book.id)
    return events
