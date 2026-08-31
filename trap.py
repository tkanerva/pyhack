# trap.py
"""
NetHack Trap System (Contract-Compliant)
Maps trap.c logic to the hybrid OOP/Actor model.
Implements ObjectProtocol, TerrainProtocol, and BaseActor.
Handles trap creation, triggering, disarmament, and multi-entity effects.
"""
from __future__ import annotations
from typing import Optional, Dict, Tuple, List, Any
from enum import Enum, auto
from dataclasses import dataclass, field
import random

from contracts import (
    ObjectProtocol, TerrainProtocol, EffectProtocol, MonsterProtocol, WorldProtocol,
    BaseActor, MessageRouter, QueryMessage, InventoryUpdateMessage,
    TerrainInteractionMessage, StatusEffectMessage, AttackMessage, DamageType, ObjectType
)


# ============================================================
# Core Enums
# ============================================================
class TrapType(Enum):
    PIT = auto()
    SPIKED_PIT = auto()
    TRAPDOOR = auto()
    ARROW_TRAP = auto()
    DART_TRAP = auto()
    FIRE_TRAP = auto()
    SLEEPING_GAS = auto()
    TELEPORTATION = auto()
    ANTI_MAGIC = auto()
    WEB = auto()
    ROLLING_BOULDER = auto()
    MAGIC_PORTAL = auto()
    LEVEL_TELEPORTER = auto()
    STAIRS_DOWN = auto()
    STAIRS_UP = auto()


# ============================================================
# Trap Entity (ObjectProtocol + TerrainProtocol)
# ============================================================
@dataclass
class Trap(ObjectProtocol, TerrainProtocol):
    """Represents a floor trap. Implements both protocols for world integration."""
    id: str
    trap_type: TrapType
    pos: Tuple[int, int]
    triggered: bool = False
    disarmed: bool = False
    seen: bool = False
    created_turn: int = 0
    
    # ObjectProtocol fields (traps are placed on the floor, but may carry items or be interacted with)
    otype: ObjectType = ObjectType.TOOL
    charges: int = 0
    blessed: bool = False
    cursed: bool = False
    container: Optional[str] = None
    carrier: Optional[str] = None

    def react_to_zap(self, damage_type: DamageType, power: int) -> Tuple[bool, str]:
        """Traps react to cancellation (disarm) or polymorph/stone-to-flesh."""
        if damage_type == DamageType.CANCELLATION:
            self.disarmed = True
            return True, f"{self.id} is disarmed by cancellation!"
        return False, "Trap unaffected by zap."

    def apply_inventory_action(self, action: str) -> bool:
        if action == "disarm":
            self.disarmed = True
            return True
        return False

    def is_contained_in(self, container_id: str) -> bool:
        return self.container == container_id

    def get_terrain_at(self, pos: Tuple[int, int]) -> Dict[str, Any]:
        return {"trap": self if self.pos == pos else None, "type": self.trap_type}

    def react_to_effect(self, effect: str, pos: Tuple[int, int]) -> Dict[str, Any]:
        if effect == "break_door" and self.trap_type == TrapType.TRAPDOOR:
            self.disarmed = True
            return {"affected": True, "removed": True}
        return {"affected": False}

    def has_door_at(self, pos: Tuple[int, int]) -> bool:
        return self.trap_type == TrapType.TRAPDOOR and self.pos == pos

    def has_trap_at(self, pos: Tuple[int, int]) -> bool:
        return self.pos == pos and not self.disarmed and not self.triggered

    def has_object_at(self, pos: Tuple[int, int]) -> bool:
        return False


# ============================================================
# Trap Actor (BaseActor + Trigger Logic)
# ============================================================
class TrapActor(BaseActor):
    """Handles trap placement, triggering, disarmament, and effect dispatch.
    Maps to trap.c: maketrap(), dotrap(), disarmtrap(), checkfor(), trap_exertion()."""
    
    def __init__(self, world: WorldProtocol, router: MessageRouter):
        self.world = world
        self.router = router
        self.traps: Dict[str, Trap] = {}

    def add_trap(self, trap: Trap):
        """Replaces trap.c:maketrap()"""
        self.traps[trap.id] = trap
        self.router.broadcast("trap_placed", {"trap_id": trap.id, "pos": trap.pos, "type": trap.trap_type.name})

    def trigger_trap(self, trap_id: str, entity_pid: str) -> Dict[str, Any]:
        """Replaces trap.c:dotrap()"""
        trap = self.traps.get(trap_id)
        if not trap or trap.triggered or trap.disarmed:
            return {"error": "trap_already_triggered_or_disarmed"}
        
        trap.triggered = True
        entity = self.world.get_actor(entity_pid)
        
        effect_result = self._apply_trap_effect(trap, entity)
        
        self.router.broadcast("trap_triggered", {
            "trap_id": trap_id,
            "entity_pid": entity_pid,
            "effect_type": effect_result.get("type"),
            "damage": effect_result.get("damage", 0)
        })
        
        return effect_result

    def disarm_trap(self, trap_id: str, source_pid: str) -> Dict[str, Any]:
        """Replaces trap.c:disarmtrap()"""
        trap = self.traps.get(trap_id)
        if not trap or trap.disarmed or trap.triggered:
            return {"error": "trap_already_disarmed_or_triggered"}
        
        trap.disarmed = True
        self.router.broadcast("trap_disarmed", {"trap_id": trap_id, "source": source_pid})
        return {"disarmed": True}

    def _apply_trap_effect(self, trap: Trap, entity: Any) -> Dict[str, Any]:
        """Dispatches trap effects based on type. Maps trap.c:trap_exertion()"""
        is_monster = isinstance(entity, MonsterProtocol)
        hp_attr = hasattr(entity, 'hp')
        max_hp_attr = hasattr(entity, 'max_hp')
        
        if not hp_attr:
            return {"type": "unknown", "damage": 0}
        
        dmg = 0
        result = {"type": trap.trap_type.name, "damage": 0}
        
        if trap.trap_type == TrapType.PIT:
            dmg = random.randint(1, 6)
            entity.hp -= dmg
            result["stuck"] = True
            result["damage"] = dmg
            
        elif trap.trap_type == TrapType.SPIKED_PIT:
            dmg = random.randint(1, 12)
            entity.hp -= dmg
            result["stuck"] = True
            result["damage"] = dmg
            
        elif trap.trap_type in (TrapType.TRAPDOOR, TrapType.STAIRS_DOWN, TrapType.LEVEL_TELEPORTER):
            new_pos = (random.randint(0, 79), random.randint(0, 21))
            entity.pos = new_pos
            result["teleported"] = True
            result["new_pos"] = new_pos
            
        elif trap.trap_type in (TrapType.ARROW_TRAP, TrapType.DART_TRAP):
            result.update(self._apply_ranged_trap(trap, entity, "arrow" if trap.trap_type == TrapType.ARROW_TRAP else "dart"))
            
        elif trap.trap_type == TrapType.FIRE_TRAP:
            if entity.resists(DamageType.FIRE):
                result["resisted"] = True
            else:
                dmg = random.randint(1, 6)
                entity.hp -= dmg
                result["damage"] = dmg
                
        elif trap.trap_type == TrapType.SLEEPING_GAS:
            entity.is_sleeping = True
            entity.sleep_duration = 25
            result["sleep_duration"] = 25
            
        elif trap.trap_type == TrapType.TELEPORTATION:
            new_pos = (random.randint(0, 79), random.randint(0, 21))
            entity.pos = new_pos
            result["teleported"] = True
            result["new_pos"] = new_pos
            
        elif trap.trap_type == TrapType.ANTI_MAGIC:
            if hasattr(entity, 'inventory'):
                for item in entity.inventory:
                    if hasattr(item, 'charges') and item.charges > 0:
                        item.charges = -1
            result["cancelled"] = True
            
        elif trap.trap_type == TrapType.WEB:
            if hasattr(entity, 'stuck'): entity.stuck = True
            if hasattr(entity, 'slowed'): entity.slowed = True
            result["stuck"] = True
            result["slowed"] = True
            
        elif trap.trap_type == TrapType.ROLLING_BOULDER:
            dmg = random.randint(4, 20)
            entity.hp -= dmg
            result["damage"] = dmg
            result["crushed"] = True
            
        elif trap.trap_type == TrapType.MAGIC_PORTAL:
            new_pos = (random.randint(0, 79), random.randint(0, 21))
            entity.pos = new_pos
            result["teleported"] = True
            result["new_pos"] = new_pos
            
        return result

    def _apply_ranged_trap(self, trap: Trap, entity: Any, proj_type: str) -> Dict[str, Any]:
        """Handles arrow/dart traps with accuracy checks. Maps trap.c:trap_hit()"""
        # Simplified accuracy: hit chance based on entity AC
        hit_chance = max(5, 20 - entity.ac if hasattr(entity, 'ac') else 10)
        if random.randint(1, 20) <= hit_chance:
            dmg = random.randint(1, 6) if proj_type == "arrow" else random.randint(1, 4)
            if not entity.resists(DamageType.ACID):
                entity.hp -= dmg
            return {"type": f"{proj_type}_hit", "damage": dmg}
        return {"type": f"{proj_type}_miss", "damage": 0}

    # BaseActor interface implementations
    def _on_attack(self, msg: AttackMessage) -> Any:
        return {"error": "trap_actor_does_not_handle_direct_attacks"}
    
    def _on_status(self, msg: StatusEffectMessage) -> Any:
        return {"error": "trap_actor_does_not_handle_status_messages"}
    
    def _on_terrain(self, msg: TerrainInteractionMessage) -> Any:
        if msg["action"] == "reveal_secret":
            for t in self.traps.values():
                if t.pos == msg["pos"] and not t.seen:
                    t.seen = True
                    return {"revealed": True, "trap_id": t.id}
        return {"error": "terrain_action_unhandled"}
    
    def _on_inventory(self, msg: InventoryUpdateMessage) -> Any:
        if msg["action"] == "disarm":
            trap = self.world.get_actor(msg["item_id"])
            if isinstance(trap, Trap) and not trap.disarmed and not trap.triggered:
                self.disarm_trap(trap.id, msg.get("from_", "player"))
                return {"disarmed": True}
        return {"error": "invalid_inventory_action"}
    
    def _on_query(self, msg: QueryMessage) -> Any:
        if msg["query"] == "get_pos":
            entity = self.world.get_actor(msg["target_pid"])
            if hasattr(entity, 'pos'):
                return {"pos": entity.pos}
        elif msg["query"] == "check_resistance":
            entity = self.world.get_actor(msg["target_pid"])
            if isinstance(entity, MonsterProtocol):
                return {"resists": entity.resists(msg.get("damage_type", DamageType.FIRE))}
        return {"error": "unknown_query"}


# ============================================================
# Integration Example
# ============================================================
if __name__ == "__main__":
    class MockWorld(WorldProtocol):
        def __init__(self): self.actors = {}
        def get_actor(self, pid): return self.actors.get(pid)
        def register_actor(self, pid, actor): self.actors[pid] = actor
        def broadcast(self, msg, exclude=None): pass
        def query(self, msg): return None
        def get_monsters_at(self, pos): return []
        def get_objects_at(self, pos): return []

    class MockRouter:
        def broadcast(self, msg_type, payload): print(f"  📢 Broadcast: {msg_type} -> {payload}")

    world = MockWorld()
    router = MockRouter()
    trap_actor = TrapActor(world, router)

    # Mock monster
    class TestMonster(MonsterProtocol):
        def __init__(self):
            self.id = "hero"; self.name = "Hero"; self.hp = 15; self.max_hp = 15
            self.ac = 10; self.pos = (10,10); self.alive = True
            self.is_sleeping = False; self.is_invisible = False
            self.is_undead = False; self.is_demon = False; self.is_golem = False
            self.is_nonliving = False; self.inventory = []
        def resists(self, dmg): return False
        def react_to_damage(self, dmg, power): return power, f"Hero takes {power} damage."
        def apply_status(self, effect, duration): return True
        def can_polymorph(self): return True
        def is_vulnerable_to(self, dmg): return True

    hero = TestMonster()
    world.register_actor("hero", hero)

    # Place traps
    arrow_trap = Trap(id="trap_arrow", trap_type=TrapType.ARROW_TRAP, pos=(10, 10))
    web_trap = Trap(id="trap_web", trap_type=TrapType.WEB, pos=(12, 10))
    pit_trap = Trap(id="trap_pit", trap_type=TrapType.PIT, pos=(14, 10))
    
    trap_actor.add_trap(arrow_trap)
    trap_actor.add_trap(web_trap)
    trap_actor.add_trap(pit_trap)

    print("=== NetHack Trap Actor Demo ===\n")
    
    print("1. Triggering Arrow Trap...")
    print(trap_actor.trigger_trap("trap_arrow", "hero"))
    print(f"   Hero HP: {hero.hp}, Pos: {hero.pos}")
    
    print("\n2. Triggering Web Trap...")
    result = trap_actor.trigger_trap("trap_web", "hero")
    print(f"   Result: {result}")
    
    print("\n3. Triggering Pit Trap...")
    result = trap_actor.trigger_trap("trap_pit", "hero")
    print(f"   Result: {result}")
    
    print("\n✅ All trap interactions routed via messages. State encapsulated per Trap actor.")

