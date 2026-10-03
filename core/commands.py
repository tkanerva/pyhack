"""Player commands: the only input the simulation accepts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union

from .types import Direction, WandType


@dataclass(frozen=True)
class MoveCommand:
    dx: int
    dy: int


@dataclass(frozen=True)
class WaitCommand:
    """A deliberate pass: no trap re-roll (unlike the old demo, where
    pressing enter re-rolled the trap under the hero's feet)."""


@dataclass(frozen=True)
class ZapCommand:
    wand_type: WandType
    direction: Direction


@dataclass(frozen=True)
class QuaffCommand:
    item_id: str


@dataclass(frozen=True)
class CastCommand:
    book_id: str
    direction: Direction


@dataclass(frozen=True)
class WearCommand:
    """Wear / put on an armor, ring or amulet (C: 'W' and 'P' both
    funnel into accessory_or_armor_on -- one command pair, PLAN-ARMOR.md
    decision 5)."""
    item_id: str


@dataclass(frozen=True)
class TakeOffCommand:
    """Take off / remove an armor, ring or amulet (C: 'T' and 'R' both
    funnel into armor_or_accessory_off)."""
    item_id: str


@dataclass(frozen=True)
class PickupCommand:
    """Pick up the topmost item on the hero's tile (C: 'g')."""


Command = Union[MoveCommand, WaitCommand, ZapCommand, QuaffCommand,
                CastCommand, WearCommand, TakeOffCommand, PickupCommand]
