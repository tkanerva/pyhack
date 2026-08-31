# potion.py
"""
NetHack Potion System (Contract-Compliant)
Maps potion.c logic to the hybrid OOP/Actor model.
Implements ObjectProtocol, EffectProtocol, and BaseActor.
"""
from __future__ import annotations
from typing import Optional, Dict, Tuple, List
from collections import defaultdict
import random

from contracts import (
    ObjectProtocol, EffectProtocol, MonsterProtocol, WorldProtocol,
    BaseActor, DamageType, ObjectType, QueryMessage, InventoryUpdateMessage,
    TerrainInteractionMessage, StatusEffectMessage, AttackMessage,
    MessageRouter
)


# ============================================================
# Potion Object (ObjectProtocol)
# ============================================================
class Potion(ObjectProtocol):
    """Represents a potion instance. Implements ObjectProtocol for world integration."""
    
    def __init__(self, otype: ObjectType, charges: int = 1, 
                 blessed: bool = False, cursed: bool = False,
                 pos: Tuple[int, int] = (0, 0), 
                 container: Optional[str] = None, carrier: Optional[str] = None):
        self.id = f"potion_{id(self)}"
        self.otype = otype
        self.charges = charges
        self.blessed = blessed
        self.cursed = cursed
        self.pos = pos
        self.container = container
        self.carrier = carrier
    
    def react_to_zap(self, damage_type: DamageType, power: int) -> Tuple[bool, str]:
        """Handle potion reactions to zaps (e.g., lightning on water, fire on oil)."""
        # Potion of water conducts lightning
        if self.otype == ObjectType.POTION and damage_type == DamageType.LIGHTNING:
            # Simplified: water conducts, oil ignites
            effect = "potion_sparks" if "water" in self.id.lower() else "potion_ignites"
            return True, f"{self.id} {effect}!"
        return False, "Potion is unaffected."
    
    def apply_inventory_action(self, action: str) -> bool:
        """Handle inventory actions. Potions are primarily consumed, not moved/equipped."""
        if action == "quaff":
            self.charges -= 1
            return True
        return False
    
    def is_contained_in(self, container_id: str) -> bool:
        return self.container == container_id


# ============================================================
# Potion Effects (EffectProtocol)
# ============================================================
class PotionEffect(EffectProtocol):
    """Base class for potion effects. Implements EffectProtocol."""
    effect_type: str = "unknown"
    damage_type: Optional[DamageType] = None
    power: int = 6
    duration: int = 0
    range: int = 1
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        return 0, f"{target.name} resists the potion effect."
    
    def apply_to_object(self, target: ObjectProtocol, world: WorldProtocol) -> Tuple[bool, str]:
        return False, "Potions don't typically affect other objects."
    
    def apply_to_terrain(self, pos: Tuple[int, int], world: WorldProtocol) -> Dict[str, Any]:
        return {"affected": False}


class HealingEffect(PotionEffect):
    effect_type = "healing"
    power = 12
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        heal = min(self.power, target.max_hp - target.hp)
        if heal > 0:
            target.hp += heal
            return heal, f"{target.name} feels better."
        return 0, f"{target.name} is already healthy."


class ConfusionEffect(PotionEffect):
    effect_type = "confusion"
    duration = 20
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        target.is_confused = True
        target.confused_duration = self.duration
        return 0, f"{target.name} feels very confused."


class PolymorphEffect(PotionEffect):
    effect_type = "polymorph"
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        if not target.can_polymorph():
            return 0, f"{target.name} is unaffected by the polymorphing potion."
        new_type = random.choice(["goblin", "orc", "troll"])
        old_hp = target.hp
        target.name = f"Polymorphed {target.name}"
        target.hp = min(old_hp, target.max_hp)
        world.broadcast({"type": "status", "effect": "polymorph", "duration": 0, "target_pid": target.id})
        return 0, f"{target.name} shudders and transforms!"


class StatGainEffect(PotionEffect):
    effect_type = "stat_gain"
    power = 1  # increases stat by 1
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        target.ac -= 1  # Simulate stat increase (AC improves)
        return 0, f"{target.name} feels stronger."


class SleepingSicknessEffect(PotionEffect):
    effect_type = "sleeping_sickness"
    duration = 15
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        target.is_sleeping = True
        target.sleep_duration = self.duration
        return 0, f"{target.name} feels sick and falls asleep."


class CancellationEffect(PotionEffect):
    effect_type = "cancellation"
    
    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        # Cancels magical items in inventory
        for item in target.inventory:
            if hasattr(item, 'charges') and item.charges > 0:
                item.charges = -1
        return 0, f"{target.name}'s magical items are cancelled!"


# ============================================================
# Potion Actor (BaseActor)
# ============================================================
class PotionActor(BaseActor):
    """Handles potion quaffing, resistance checks, and side effects.
    Maps directly to potion.c functions: quaff(), quaffmon(), potion_inverts(), etc."""
    
    def __init__(self, world: WorldProtocol, router: MessageRouter):
        self.world = world
        self.router = router
        self.effect_map = {
            "healing": HealingEffect,
            "confusion": ConfusionEffect,
            "polymorph": PolymorphEffect,
            "stat_gain": StatGainEffect,
            "sleeping_sickness": SleepingSicknessEffect,
            "cancellation": CancellationEffect,
        }
    
    def quaff(self, potion: Potion, target: MonsterProtocol, is_monster: bool = False) -> Tuple[int, str]:
        """Main entry point. Replaces potion.c:quaff() and quaffmon()."""
        if potion.charges <= 0:
            return 0, "The potion has no charges."
        
        # Handle cursed/blessed inversion
        self._handle_inversion(potion)
        
        # Check resistance
        if target.resists(DamageType.POISON) or (potion.cursed and not potion.blessed):
            if random.randint(1, 100) <= 15:  # 15% chance to resist shatter/quaff
                return 0, f"{target.name} resists the potion's effect."
        
        # Determine effect type
        effect_name = self._determine_effect(potion)
        effect_cls = self.effect_map.get(effect_name)
        if not effect_cls:
            return 0, "The potion has an unknown effect."
        
        effect = effect_cls()
        damage, msg = effect.apply_to_monster(target, self.world)
        
        # Handle side effects (poison, stat changes, etc.)
        if potion.cursed and not potion.blessed:
            self._apply_cursed_side_effects(target)
        
        # Update state
        potion.charges -= 1
        if potion.charges <= 0 and not potion.cursed:
            potion.charges = -1  # Mark as consumed
        
        # Broadcast to world
        self.router.broadcast("potion_quaffed", {
            "potion_id": potion.id,
            "target_pid": target.id,
            "effect": effect_name,
            "is_monster": is_monster
        })
        
        return damage, msg
    
    def _handle_inversion(self, potion: Potion):
        """Replaces potion.c:potion_inverts()"""
        if potion.blessed and not potion.cursed:
            potion.blessed = False
            potion.cursed = True
        elif potion.cursed and not potion.blessed:
            potion.blessed = True
            potion.cursed = False
    
    def _determine_effect(self, potion: Potion) -> str:
        """Maps potion type to effect name. In production, this would query a registry."""
        type_map = {
            ObjectType.POTION: "healing",  # Simplified; real impl maps otyp -> effect
        }
        return type_map.get(potion.otype, "confusion")
    
    def _apply_cursed_side_effects(self, target: MonsterProtocol):
        """Handles cursed potion side effects: poison, stat loss, confusion."""
        poison_chance = random.randint(1, 100)
        if poison_chance <= 30:
            self.poison(target, 15)
        elif poison_chance <= 50:
            target.ac += 1  # Simulate stat loss
        elif poison_chance <= 70:
            target.is_confused = True
            target.confused_duration = 10
    
    def poison(self, target: MonsterProtocol, duration: int):
        """Replaces potion.c:poison()"""
        target.poisoned = True
        target.poison_duration = duration
        self.router.broadcast("poison_applied", {"target_pid": target.id, "duration": duration})
    
    # BaseActor interface implementations
    def _on_attack(self, msg: AttackMessage) -> Any:
        return {"error": "potion_actor_does_not_handle_attacks"}
    
    def _on_status(self, msg: StatusEffectMessage) -> Any:
        return {"error": "potion_actor_does_not_handle_status_messages"}
    
    def _on_terrain(self, msg: TerrainInteractionMessage) -> Any:
        return {"error": "potion_actor_does_not_handle_terrain_messages"}
    
    def _on_inventory(self, msg: InventoryUpdateMessage) -> Any:
        if msg["action"] == "quaff":
            potion = self.world.get_actor(msg["item_id"])
            if isinstance(potion, Potion):
                # Find target (simplified: assume player or nearest monster)
                target_pid = msg.get("to") or msg.get("from")
                target = self.world.get_actor(target_pid)
                if target and isinstance(target, MonsterProtocol):
                    dmg, msg_out = self.quaff(potion, target)
                    return {"quaffed": True, "damage": dmg, "message": msg_out}
        return {"error": "invalid_inventory_action"}
    
    def _on_query(self, msg: QueryMessage) -> Any:
        if msg["query"] == "check_resistance":
            target = self.world.get_actor(msg["target_pid"])
            if isinstance(target, MonsterProtocol):
                return {"resists": target.resists(DamageType.POISON)}
        return {"error": "unknown_query"}


# ============================================================
# Integration Example
# ============================================================
if __name__ == "__main__":
    # Mock world/router for demonstration
    class MockWorld(WorldProtocol):
        def __init__(self): self.actors = {}
        def get_actor(self, pid): return self.actors.get(pid)
        def register_actor(self, pid, actor): self.actors[pid] = actor
        def broadcast(self, msg, exclude=None): pass
        def query(self, msg): return None
        def get_monsters_at(self, pos): return []
        def get_objects_at(self, pos): return []
    
    class MockRouter:
        def broadcast(self, msg_type, payload): pass
    
    world = MockWorld()
    router = MockRouter()
    potion_actor = PotionActor(world, router)
    
    # Create test monster & potion
    from contracts import MonsterProtocol
    class TestMonster(MonsterProtocol):
        def __init__(self):
            self.id = "hero"; self.name = "Hero"; self.hp = 10; self.max_hp = 10
            self.ac = 10; self.pos = (10,10); self.alive = True
            self.is_sleeping = False; self.is_invisible = False
            self.is_undead = False; self.is_demon = False; self.is_golem = False
            self.is_nonliving = False; self.inventory = []
            self.confused = False; self.confused_duration = 0
            self.poisoned = False; self.poison_duration = 0
            
        def resists(self, dmg): return False
        def react_to_damage(self, dmg, power): return power, f"Hero takes {power} damage."
        def apply_status(self, effect, duration): return True
        def can_polymorph(self): return True
        def is_vulnerable_to(self, dmg): return True
    
    hero = TestMonster()
    world.register_actor("hero", hero)
    
    potion = Potion(ObjectType.POTION, charges=1, cursed=True, pos=(10, 10))
    world.register_actor(potion.id, potion)
    
    dmg, msg = potion_actor.quaff(potion, hero, is_monster=False)
    print(f"Quaffed potion: {msg} | HP: {hero.hp}")

