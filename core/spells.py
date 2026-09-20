"""Spell system: cast_spell() with simple straight-line beam traversal.

Ported from the old spell.py.  Differences (documented in
ARCHITECTURE.md): beams stop at the FIRST monster hit (NetHack
behaviour; the old beam hit everything in range), damage is a flat 2d6
(the old d6*nd formula referenced an 'nd' stat that never existed), and
the study/learning mechanics are dropped (charges only).
"""
from __future__ import annotations

from typing import List, Optional

from .events import Event, MessageEvent
from .items import cancel_items, consume_item
from .rules import (apply_damage, can_polymorph, find_target_in_line, heal,
                    put_to_sleep, resists, roll, teleport_to_floor)
from .types import DamageType, Direction, Item, ObjectType, SpellType, World

BEAM_RANGE = 7
HEALING_POWER = 12

SPELL_DAMAGE = {
    SpellType.MAGIC_MISSILE: DamageType.MAGIC_MISSILE,
    SpellType.CONE_OF_COLD: DamageType.COLD,
    SpellType.LIGHTNING: DamageType.LIGHTNING,
    SpellType.DEATH: DamageType.DEATH,
}


def _find_book(world: World, caster_id: str, book_id: str) -> Optional[Item]:
    item = world.items.get(book_id)
    if item is None or item.otype != ObjectType.BOOK or item.container != caster_id:
        return None
    return item


def _miss_message(hit_wall: bool, noun: str = "spell") -> str:
    return f"💥 The {noun} hits a wall." if hit_wall else f"The {noun} goes astray."


def cast_spell(world: World, caster_id: str, book_id: str,
               direction: Direction, rng) -> List[Event]:
    book = _find_book(world, caster_id, book_id)
    if book is None:
        return [MessageEvent("You don't have such a book.")]
    if book.charges <= 0:
        return [MessageEvent("The book is blank.")]

    caster = world.actors[caster_id]
    st = book.spell_type or SpellType.MAGIC_MISSILE
    spell_name = st.name.lower().replace("_", " ")
    events: List[Event] = [MessageEvent(
        f"You cast {spell_name}." if caster.is_hero
        else f"{caster.name} casts {spell_name}.")]

    if st == SpellType.FIREBALL:
        # immediate area effect: everything adjacent to the caster
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
    elif st in SPELL_DAMAGE:
        # resolve the beam first; dice are only rolled when the spell
        # actually connects (as in NetHack's spell_hit())
        target, hit_wall = find_target_in_line(world, caster.pos, direction, BEAM_RANGE)
        if target is None:
            events.append(MessageEvent(_miss_message(hit_wall)))
        elif resists(target, SPELL_DAMAGE[st]):
            events.append(MessageEvent(f"{target.name} is unaffected."))
        else:
            dmg = roll(rng, 6, 2)
            events += apply_damage(world, target.id, dmg, SPELL_DAMAGE[st],
                                   f"spell:{spell_name}")
    elif st == SpellType.SLEEP:
        target, hit_wall = find_target_in_line(world, caster.pos, direction, BEAM_RANGE)
        if target is None:
            events.append(MessageEvent(_miss_message(hit_wall, "ray")))
        elif resists(target, DamageType.SLEEP):
            events.append(MessageEvent(f"{target.name} resists sleep!"))
        else:
            events += put_to_sleep(world, target.id, 25)
    elif st == SpellType.HEALING:
        events += heal(world, caster_id, HEALING_POWER)
    elif st == SpellType.TELEPORT:
        events += teleport_to_floor(world, caster_id, rng)
    elif st == SpellType.POLYMORPH:
        target, hit_wall = find_target_in_line(world, caster.pos, direction, BEAM_RANGE)
        if target is None:
            events.append(MessageEvent(_miss_message(hit_wall, "ray")))
        elif not can_polymorph(target):
            events.append(MessageEvent(f"{target.name} cannot be polymorphed!"))
        else:
            target.name = f"Polymorphed {target.name}"
            events.append(MessageEvent(f"{target.name} shudders and transforms!"))
    elif st == SpellType.CANCELLATION:
        # cancellation affects the caster (NetHack behaviour)
        events += cancel_items(world, caster)

    book.charges -= 1
    if book.charges <= 0:
        consume_item(world, caster_id, book.id)
    return events
