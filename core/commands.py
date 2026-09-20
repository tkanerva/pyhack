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


Command = Union[MoveCommand, WaitCommand, ZapCommand, QuaffCommand, CastCommand]
