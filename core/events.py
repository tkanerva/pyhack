"""Events: the side effects a turn produces, returned as plain data.

The simulation never prints or broadcasts -- it returns a list of
Events.  The UI (or a test) consumes them.  This is what replaces the
old MessageRouter / world.broadcast machinery: same decoupling, but the
flow is visible in one return value and trivially assertable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .types import DamageType, WandType


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
class TrapTriggeredEvent(Event):
    trap_id: str
    actor_id: str


@dataclass(frozen=True)
class TrapSeenEvent(Event):
    trap_id: str


@dataclass(frozen=True)
class ZapEvent(Event):
    caster: str
    wand_type: WandType
    target: Optional[str]


@dataclass(frozen=True)
class GameOverEvent(Event):
    victory: bool
    reason: str
