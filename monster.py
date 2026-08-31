# monster.py
"""
NetHack Monsters (Contract-Compliant)
Lightweight monster implementation satisfying MonsterProtocol.
Handles movement, trap triggering, and basic combat.
"""
from __future__ import annotations
from typing import Tuple, List
from dataclasses import dataclass, field
import random

from contracts import MonsterProtocol, DamageType
from trap import TrapType
from player import Hero


@dataclass
class SimpleMonster(MonsterProtocol):
    """Base monster satisfying MonsterProtocol."""
    name: str
    hp: int
    max_hp: int
    ac: int
    pos: Tuple[int, int]
    damage: int = 2
    speed: int = 1
    alive: bool = True
    is_sleeping: bool = False
    is_invisible: bool = False
    is_undead: bool = False
    is_demon: bool = False
    is_golem: bool = False
    is_nonliving: bool = False
    inventory: List[object] = field(default_factory=list)
    id: str = "monster"
    sleep_duration: int = 0
    stuck: bool = False
    slowed: bool = False
    last_messages: List[str] = field(default_factory=list)

    # ✅ MonsterProtocol implementation
    def resists(self, dmg: DamageType) -> bool:
        return False

    def react_to_damage(self, dmg: DamageType, power: int) -> Tuple[int, str]:
        self.hp = max(0, self.hp - power)
        if self.hp <= 0:
            self.alive = False
        return power, f"{self.name} takes {power} damage!"

    def apply_status(self, effect: str, duration: int) -> bool:
        if effect == "sleep":
            self.is_sleeping = True
            self.sleep_duration = duration
            return True
        return False

    def can_polymorph(self) -> bool:
        return False

    def is_vulnerable_to(self, dmg: DamageType) -> bool:
        return not self.resists(dmg)

    # ✅ Movement & Trap Triggering
    def move(self, world_map: list) -> bool:
        dirs = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = self.pos[0] + dx, self.pos[1] + dy
            if 0 <= nx < len(world_map[0]) and 0 <= ny < len(world_map):
                if world_map[ny][nx] != 1:  # 1 = wall
                    self.pos = (nx, ny)
                    return True
        return False

    def check_and_trigger_traps(self, world: "DemoWorld"):
        """Monsters trigger traps when stepping on them."""
        for trap in world.traps:
            if trap.pos == self.pos and not trap.triggered and not trap.disarmed:
                if random.randint(1, 100) <= 30:  # 30% trigger chance
                    result = world.trap_actor.trigger_trap(trap.id, self.id)
                    dmg = result.get("damage", 0)
                    if dmg > 0:
                        print("DAMAGEE!!!!", "!"*120)
                        msg = self._format_trap_message(trap.trap_type, dmg)
                        self.last_messages.append(msg)
                        dmg_type = DamageType.FIRE if trap.trap_type == TrapType.FIRE_TRAP else DamageType.ACID
                        self.react_to_damage(dmg_type, dmg)

    def attack(self, target: MonsterProtocol) -> int:
        """Simple attack with AC-based hit chance."""
        if random.randint(1, 20) <= 20 - target.ac:
            dmg = random.randint(1, self.damage)
            _, _ = target.react_to_damage(DamageType.FIRE, dmg)
            return dmg
        return 0

    def _format_trap_message(self, trap_type, dmg):
        tnames = {
            TrapType.PIT: "pit", TrapType.SPIKED_PIT: "spiked pit",
            TrapType.FIRE_TRAP: "fire", TrapType.ARROW_TRAP: "arrow",
            TrapType.WEB: "web", TrapType.ROLLING_BOULDER: "boulder"
        }
        t = tnames.get(trap_type, "trap")
        return f"⚡ {self.name} triggers a {t} and takes {dmg} damage!"


# Concrete monster types
class Goblin(SimpleMonster):
    def __init__(self, pos):
        super().__init__(name="Goblin", hp=8, max_hp=8, ac=7, pos=pos, damage=2)
        self.last_messages = []

class Orc(SimpleMonster):
    def __init__(self, pos):
        super().__init__(name="Orc", hp=15, max_hp=15, ac=5, pos=pos, damage=4)
        self.last_messages = []

class Bat(SimpleMonster):
    def __init__(self, pos):
        super().__init__(name="Bat", hp=4, max_hp=4, ac=3, pos=pos, damage=1)
        self.is_flying = True
        self.last_messages = []

