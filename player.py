
# player.py
"""
NetHack Hero (Contract-Compliant)
Minimal player implementation satisfying MonsterProtocol.
Includes message logging for trap interactions and combat.
"""
from __future__ import annotations
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
import random

from contracts import MonsterProtocol, DamageType, QueryMessage
from trap import TrapType


@dataclass
class Hero(MonsterProtocol):
    """Player entity. Implements all MonsterProtocol requirements."""
    pos: Tuple[int, int]
    hp: int = 20
    max_hp: int = 20
    ac: int = 5
    alive: bool = True
    is_sleeping: bool = False
    is_invisible: bool = False
    is_undead: bool = False
    is_demon: bool = False
    is_golem: bool = False
    is_nonliving: bool = False
    inventory: List[object] = field(default_factory=list)
    
    # Optional status tracking
    sleep_duration: int = 0
    confused: bool = False
    poisoned: bool = False
    poison_duration: int = 0
    stuck: bool = False
    slowed: bool = False
    
    id: str = "player"
    name: str = "Hero"
    
    # Message buffer for UI
    last_messages: List[str] = field(default_factory=list, init=False)

    def resists(self, dmg: DamageType) -> bool:
        return False

    def react_to_damage(self, dmg: DamageType, power: int) -> Tuple[int, str]:
        self.hp = max(0, self.hp - power)
        if self.hp <= 0:
            self.alive = False
        msg = f"⚠️  You take {power} damage!"
        return power, msg

    def apply_status(self, effect: str, duration: int) -> bool:
        if effect == "sleep":
            self.is_sleeping = True
            self.sleep_duration = duration
            self.last_messages.append("🛌 You feel very sleepy!")
            return True
        return False

    def can_polymorph(self) -> bool:
        return False

    def is_vulnerable_to(self, dmg: DamageType) -> bool:
        return not self.resists(dmg)

    def move(self, dx: int, dy: int, world_map: list) -> bool:
        new_x, new_y = self.pos[0] + dx, self.pos[1] + dy
        if 0 <= new_x < len(world_map[0]) and 0 <= new_y < len(world_map):
            if world_map[new_y][new_x] != 1:
                self.pos = (new_x, new_y)
                return True
        return False

    #def take_damage_until_death(self, world: "DemoWorld"):
    def check_and_trigger_traps(self, world: "DemoWorld"):
        """Auto-trigger traps at current position and log messages."""
        for trap in world.traps:
            if trap.pos == self.pos and not trap.triggered and not trap.disarmed:
                if random.randint(1, 100) <= 30:
                    result = world.trap_actor.trigger_trap(trap.id, self.id)
                    dmg = result.get("damage", 0)
                    if dmg > 0:
                        msg = self._format_trap_message(trap.trap_type, dmg)
                        self.last_messages.append(msg)
                        # Also apply damage via react_to_damage so HP syncs with message
                        self.react_to_damage(DamageType.FIRE if trap.trap_type == TrapType.FIRE_TRAP else DamageType.ACID, dmg)
                else:
                    trap.seen = True
                    self.last_messages.append("👣 You feel something underfoot but don't trigger it.")
                    
            elif trap.pos == self.pos and trap.triggered and not trap.disarmed:
                # Standing on a triggered trap (e.g., web, pit)
                if trap.trap_type == TrapType.WEB:
                    msg = "🕸️  You are stuck in a web!"
                    self.last_messages.append(msg)
                elif trap.trap_type in (TrapType.PIT, TrapType.SPIKED_PIT):
                    msg = f"🕳️  You are stuck in a {trap.trap_type.name.replace('_', ' ').lower()}!"
                    self.last_messages.append(msg)
        
        # Keep only last 5 messages
        if len(self.last_messages) > 5:
            self.last_messages = self.last_messages[-5:]

    def _format_trap_message(self, trap_type: TrapType, damage: int) -> str:
        type_names = {
            TrapType.PIT: "pit",
            TrapType.SPIKED_PIT: "spiked pit",
            TrapType.FIRE_TRAP: "fire",
            TrapType.ARROW_TRAP: "arrow",
            TrapType.DART_TRAP: "dart",
            TrapType.ROLLING_BOULDER: "rolling boulder",
        }
        tname = type_names.get(trap_type, "trap")
        return f"⚡  A {tname} hits you for {damage} damage!"

