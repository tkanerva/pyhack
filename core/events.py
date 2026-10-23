"""Events: the side effects a turn produces, returned as plain data.

The simulation never prints or broadcasts -- it returns a list of
Events.  The UI (or a test) consumes them.  This is what replaces the
old MessageRouter / world.broadcast machinery: same decoupling, but the
flow is visible in one return value and trivially assertable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import DamageType, ZapEffect


class Event:
    """Marker base class so consumers can type-check with isinstance."""


@dataclass(frozen=True)
class MessageEvent(Event):
    """A line for the message log / player-facing text."""
    text: str


@dataclass(frozen=True)
class DamageEvent(Event):
    target: str
    amount: int
    damage_type: DamageType
    source: str  # actor id, "trap:trap_0", "zap:fire", "poison", ...


@dataclass(frozen=True)
class DeathEvent(Event):
    target: str
    by: str


@dataclass(frozen=True)
class StatusEvent(Event):
    target: str
    effect: str  # "sleep" | "stuck" | "poison" | "confusion" | "teleport"
    duration: int


@dataclass(frozen=True)
class DiscoveryEvent(Event):
    """An object-identity discovery intent (C: the makeknown() /
    observe_object() calls of learnring in src/do_wear.c).

    The ring / item side (core.rings) only DECIDES what is discovered and
    emits this intent; the mutation is applied by the core choke point
    ``core.rules.apply_discovery`` through ``process_events`` -- exactly
    the DamageEvent / StatusEvent pattern.  This is what keeps the
    ``Item.dknown`` / ``Item.known`` and the per-game ``oc_name_known`` /
    ``oc_encountered`` mutations out of the ring module and in the core.

    Fields (what changes):
    - ``otyp``: the Object type -- the C objects[otyp] row whose
      oc_name_known / oc_encountered are updated;
    - ``item_id``: the specific Item to mark seen (Item.dknown);
    - ``mark_known``: set the type's oc_name_known (C: makeknown);
    - ``mark_encountered``: mark the type / item encountered (C:
      observe_object -- the item is dknown);
    - ``reveal_spe``: reveal the enchantment (Item.known) for a charged
      ring whose type is now known.
    """
    otyp: int
    item_id: Optional[str] = None
    mark_known: bool = False
    mark_encountered: bool = False
    reveal_spe: bool = False


@dataclass(frozen=True)
class TrapTriggeredEvent(Event):
    trap_id: str
    actor_id: str


@dataclass(frozen=True)
class TrapSeenEvent(Event):
    trap_id: str


@dataclass(frozen=True)
class ZapEvent(Event):
    """A beam was fired (wand zap or spell cast -- the shared engine
    emits it; the effect is the registry key, C: the zap type)."""
    caster: str
    effect: ZapEffect
    target: Optional[str]


@dataclass(frozen=True)
class LevelChangeEvent(Event):
    """The hero changed dungeon level (C: the goto_level transition).

    ``lev`` is the level now occupied (C: u.uz after the transition);
    ``first_visit`` is True when the level was generated for this
    entry (C: the mklev() vs getlev() branch of goto_level).
    """
    lev: int
    first_visit: bool


@dataclass(frozen=True)
class GameOverEvent(Event):
    victory: bool
    reason: str
