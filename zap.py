
"""
NetHack-style Zap System (Hybrid OOP)
- Fast boolean type checks via class attributes
- Clear inheritance hierarchy for behavioral polymorphism
- Optional metadata for serialization, AI routing, or UI tags
- Decoupled zap/spell system that queries monster interfaces
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, ClassVar


# ============================================================
# Core Enums
# ============================================================
class DamageType(Enum):
    MAGIC_MISSILE = auto()
    FIRE = auto()
    COLD = auto()
    SLEEP = auto()
    DEATH = auto()
    LIGHTNING = auto()
    POISON = auto()
    ACID = auto()

class WandType(Enum):
    STRIKING = "force_bolt"
    CANCELLATION = "cancellation"
    TELEPORTATION = "teleport"
    MAKE_INVISIBLE = "invisibility"
    POLYMORPH = "polymorph"
    SLEEP = "sleep"
    SLOW_MONSTER = "slow"
    SPEED_MONSTER = "haste"
    UNDEAD_TURNING = "undead_turning"
    OPENING = "opening"
    LOCKING = "locking"
    PROBING = "probe"
    FIRE = "fire_bolt"
    COLD = "cone_of_cold"
    LIGHTNING = "lightning_bolt"
    DEATH = "death_ray"
    DIGGING = "dig"
    NOTHING = "null"


# ============================================================
# Monster Base & Type Hierarchy
# ============================================================
@dataclass
class Monster:
    """Base entity. All type flags default to False, overridden by subclasses."""
    name: str
    hp: int
    max_hp: int
    ac: int = 10
    pos: Tuple[int, int] = (0, 0)
    alive: bool = True
    is_sleeping: bool = False
    is_invisible: bool = False
    inventory: List[object] = field(default_factory=list)
    
    # Fast boolean type checks (class-level, inherited automatically)
    is_undead: ClassVar[bool] = False
    is_demon: ClassVar[bool] = False
    is_golem: ClassVar[bool] = False
    is_humanoid: ClassVar[bool] = False
    is_nonliving: ClassVar[bool] = False
    is_flying: ClassVar[bool] = False
    is_swimmer: ClassVar[bool] = False
    
    # Optional metadata
    type_tag: str = "default"
    material: str = ""
    level: int = 1

    # Polymorphic interface
    def resists(self, dmg: DamageType) -> bool:
        """Override in subclasses for type-specific resistance"""
        return False

    def react_to_damage(self, dmg: DamageType, amount: int) -> Tuple[int, str]:
        """Default damage reaction. Override for special behavior."""
        if self.resists(dmg):
            return 0, f"{self.name} resists {dmg.name.lower()}!"
        
        self.hp = max(0, self.hp - amount)
        if self.hp == 0:
            self.alive = False
            return amount, f"{self.name} dies!"
        return amount, f"{self.name} takes {amount} {dmg.name.lower()} damage."

    def wake_up(self): self.is_sleeping = False
    def take_polymorph(self) -> bool: return False
    def is_vulnerable_to(self, dmg: DamageType) -> bool: return not self.resists(dmg)


# ============================================================
# Concrete Monster Types (Hybrid: Flags + Inheritance)
# ============================================================
class UndeadMonster(Monster):
    is_undead = True
    is_nonliving = True
    type_tag = "undead"

    def resists(self, dmg: DamageType) -> bool:
        return dmg in (DamageType.MAGIC_MISSILE, DamageType.COLD, DamageType.LIGHTNING)

    def react_to_damage(self, dmg: DamageType, amount: int) -> Tuple[int, str]:
        if dmg == DamageType.DEATH:
            self.hp = min(self.max_hp, self.hp + amount)
            return 0, f"{self.name} absorbs the deadly energy!"
        return super().react_to_damage(dmg, amount)


class DemonMonster(Monster):
    is_demon = True
    type_tag = "demon"

    def resists(self, dmg: DamageType) -> bool:
        return dmg in (DamageType.FIRE, DamageType.DEATH, DamageType.SLEEP)

    def take_polymorph(self) -> bool:
        return True  # Cannot be polymorphed


class GolemMonster(Monster):
    is_golem = True
    type_tag = "golem"
    material = "stone"  # metadata

    def resists(self, dmg: DamageType) -> bool:
        return dmg in (DamageType.SLEEP, DamageType.DEATH, DamageType.ACID)

    def wake_up(self):
        pass  # Golems don't sleep naturally


class HumanoidMonster(Monster):
    is_humanoid = True
    type_tag = "humanoid"


class FlyingMonster(Monster):
    is_flying = True
    type_tag = "flying"

    def is_vulnerable_to(self, dmg: DamageType) -> bool:
        # Flying creatures often avoid ground-based effects
        if dmg in (DamageType.ACID, DamageType.POISON):
            return self.ac < 10  # Simplified vulnerability logic
        return super().is_vulnerable_to(dmg)


class SwimmingMonster(Monster):
    is_swimmer = True
    type_tag = "swimmer"

    def react_to_damage(self, dmg: DamageType, amount: int) -> Tuple[int, str]:
        if dmg == DamageType.FIRE:
            # Water conducts lightning, extinguishes fire
            return 0, f"{self.name} is in water, fire fizzles!"
        return super().react_to_damage(dmg, amount)


# ============================================================
# Zap/Spell System (Polymorphic Dispatch)
# ============================================================
@dataclass
class ZapEffect:
    """Base class for all zap/spell effects. Queries monster polymorphically."""
    dmg_type: Optional[DamageType] = None
    duration: int = 0
    power: int = 6

    def apply(self, target: Monster) -> Tuple[int, str]:
        raise NotImplementedError


class DamageZap(ZapEffect):
    def apply(self, target: Monster) -> Tuple[int, str]:
        return target.react_to_damage(self.dmg_type, self.power)


class StatusZap(ZapEffect):
    """Handles non-damage effects like sleep, slow, teleport, etc."""
    effect_name: str = ""
    
    def apply(self, target: Monster) -> Tuple[int, str]:
        if target.resists(self.dmg_type or DamageType.SLEEP):
            return 0, f"{target.name} resists {self.effect_name}!"
        
        if self.dmg_type == DamageType.SLEEP:
            target.is_sleeping = True
            return 0, f"{target.name} falls asleep!"
        
        if self.dmg_type == DamageType.CANCELLATION:
            for item in target.inventory:
                if hasattr(item, 'charges'):
                    item.charges = -1
            return 0, f"{target.name}'s magical items are cancelled!"
        
        if self.dmg_type == DamageType.TELEPORTATION:
            import random
            new_pos = (random.randint(0, 79), random.randint(0, 21))
            target.pos = new_pos
            return 0, f"{target.name} is teleported to {new_pos}!"
        
        if self.dmg_type == DamageType.POLYMORPH:
            if target.take_polymorph():
                return 0, f"{target.name} cannot be polymorphed!"
            return 0, f"{target.name} shudders and transforms!"
        
        return 0, f"{target.name} is affected by {self.effect_name}."


class HealingZap(ZapEffect):
    def apply(self, target: Monster) -> Tuple[int, str]:
        heal = min(self.power, target.max_hp - target.hp)
        target.hp += heal
        return heal, f"{target.name} recovers {heal} HP."


class UndeadTurningZap(StatusZap):
    dmg_type = DamageType.SLEEP
    effect_name = "undead turning"
    
    def apply(self, target: Monster) -> Tuple[int, str]:
        if not target.is_undead:
            return 0, f"{target.name} is unaffected by undead turning."
        target.flee() if hasattr(target, 'flee') else None
        damage = 0
        return damage, f"{target.name} is turned and flees!"


# ============================================================
# Wand/Spell Orchestrator
# ============================================================
class Wand:
    def __init__(self, wand_type: WandType, charges: int = 0, spell: ZapEffect | None = None):
        self.wand_type = wand_type
        self.charges = charges
        self.spell = spell or self._create_spell(wand_type)
    
    def _create_spell(self, wtype: WandType) -> ZapEffect:
        damage_map = {
            WandType.FIRE: DamageType.FIRE,
            WandType.COLD: DamageType.COLD,
            WandType.LIGHTNING: DamageType.LIGHTNING,
            WandType.DEATH: DamageType.DEATH,
            WandType.STRIKING: DamageType.FIRE,  # Force bolt = fire-like impact
            WandType.SLEEP: DamageType.SLEEP,
            WandType.CANCELLATION: DamageType.CANCELLATION,
            WandType.TELEPORTATION: DamageType.TELEPORTATION,
            WandType.POLYMORPH: DamageType.POLYMORPH,
        }
        dmg = damage_map.get(wtype)
        
        if dmg:
            if dmg in (DamageType.SLEEP, DamageType.CANCELLATION, DamageType.TELEPORTATION, DamageType.POLYMORPH):
                return StatusZap(dmg_type=dmg, power=0, effect_name=wtype.value)
            return DamageZap(dmg_type=dmg, power=6)
        
        if wtype == WandType.UNDEAD_TURNING:
            return UndeadTurningZap(power=0)
        if wtype == WandType.HEALING:
            return HealingZap(power=8)
        if wtype == WandType.DIGGING:
            return StatusZap(dmg_type=DamageType.FIRE, effect_name="digging")
        
        return StatusZap(power=0, effect_name=wtype.value)
    
    def zap(self, target: Monster, power_override: int = 0) -> Tuple[int, str]:
        if self.charges <= 0:
            return 0, f"{self.spell.__class__.__name__} has no charges."
        self.charges -= 1
        power = power_override or self.spell.power
        return self.spell.apply(target)


# ============================================================
# World/Context (Minimal, for demonstration)
# ============================================================
class GameWorld:
    def __init__(self):
        self.monsters: List[Monster] = []
        self.wands: Dict[str, Wand] = {}
    
    def add_monster(self, m: Monster):
        self.monsters.append(m)
    
    def add_wand(self, name: str, wand: Wand):
        self.wands[name] = wand
    
    def zap_at(self, wand_name: str, target: Monster, power: int = 0) -> Tuple[int, str]:
        if wand_name not in self.wands:
            return 0, f"Unknown wand: {wand_name}"
        return self.wands[wand_name].zap(target, power)


# ============================================================
# Demo: Polymorphic Zap System
# ============================================================
def demo():
    world = GameWorld()
    
    # Create monsters
    skeletons = [
        UndeadMonster("Skeleton", 6, 6, level=2),
        UndeadMonster("Lich", 15, 15, ac=4, level=8),
    ]
    
    demons = [
        DemonMonster("Imp", 4, 4, level=1),
        DemonMonster("Barbed Devil", 25, 25, ac=5, level=6),
    ]
    
    golems = [
        GolemMonster("Stone Golem", 18, 18, ac=6, material="stone", level=5),
        GolemMonster("Flesh Golem", 14, 14, ac=7, material="flesh", level=4),
    ]
    
    humans = [
        HumanoidMonster("Goblin", 8, 8, level=1),
        HumanoidMonster("Orc Warrior", 12, 12, ac=8, level=3),
    ]
    
    flyers = [
        FlyingMonster("Giant Bat", 7, 7, level=2),
    ]
    
    swimmers = [
        SwimmingMonster("Water Nymph", 10, 10, level=3),
    ]
    
    targets = skeletons + demons + golems + humans + flyers + swimmers
    
    # Setup wands
    world.add_wand("fire", Wand(WandType.FIRE, charges=10))
    world.add_wand("death", Wand(WandType.DEATH, charges=3))
    world.add_wand("sleep", Wand(WandType.SLEEP, charges=5))
    world.add_wand("teleport", Wand(WandType.TELEPORTATION, charges=2))
    world.add_wand("polymorph", Wand(WandType.POLYMORPH, charges=1))
    world.add_wand("undead_turning", Wand(WandType.UNDEAD_TURNING, charges=4))
    
    print("=== NetHack Hybrid OOP Zap Demo ===\n")
    
    for zap_name in ["fire", "death", "sleep", "teleport", "polymorph", "undead_turning"]:
        print(f"\n🔹 {zap_name.upper()} ZAP")
        print("-" * 40)
        for m in targets:
            if not m.alive:
                continue
            damage, msg = world.zap_at(zap_name, m)
            # Clean output
            msg = msg.replace(f"{m.name} ", "")
            print(f"  {m.name:15} | HP: {m.hp:2}/{m.max_hp:2} | {msg}")
    
    print("\n✅ All state transitions handled via polymorphic interfaces.")
    print("✅ Fast boolean checks via class attributes (type(self).is_undead, etc.)")
    print("✅ No global flags, no callback parsing, fully decoupled zap system.")


if __name__ == "__main__":
    demo()

