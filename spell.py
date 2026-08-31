
# spell.py
"""
NetHack Spell System (Contract-Compliant)
Maps spell.c logic to the hybrid OOP/Actor model.
Implements ObjectProtocol, EffectProtocol, and BaseActor.
Casting, skill scaling, beam traversal, and book consumption are fully decoupled.
"""
from __future__ import annotations
from typing import Optional, Dict, Tuple, List, ClassVar
from enum import Enum, auto
from dataclasses import dataclass, field
import random

from contracts import (
    ObjectProtocol, EffectProtocol, MonsterProtocol, WorldProtocol,
    BaseActor, MessageRouter, DamageType, ObjectType, QueryMessage,
    InventoryUpdateMessage, TerrainInteractionMessage, StatusEffectMessage,
    AttackMessage
)


# ============================================================
# Core Enums & Skill Levels
# ============================================================
class SpellSkill(Enum):
    RESTRICTED = 0
    UNSKILLED = 1
    BASIC = 2
    SKILLED = 3
    EXPERT = 4

class SpellType(Enum):
    MAGIC_MISSILE = auto()
    FIREBALL = auto()
    CONE_OF_COLD = auto()
    SLEEP = auto()
    DEATH = auto()
    LIGHTNING = auto()
    POLYMORPH = auto()
    CANCELLATION = auto()
    TELEPORT = auto()
    HEALING = auto()
    DRAIN_LIFE = auto()
    STONE_TO_FLESH = auto()
    NOVEL = auto()


# ============================================================
# Spellbook (ObjectProtocol)
# ============================================================
@dataclass
class Spellbook(ObjectProtocol):
    """Represents a spellbook/novel. Implements ObjectProtocol for world integration."""
    otype: ObjectType = ObjectType.BOOK
    spell_type: SpellType = SpellType.MAGIC_MISSILE
    learned: bool = False
    studied: int = 0  # Acts as charges/study level in spell.c
    is_novel: bool = False  # Special handling for novels vs spellbooks
    _charges: int = field(default=1, init=False)

    def __post_init__(self):
        self.id = f"book_{id(self)}"
        self.charges = self._charges

    def react_to_zap(self, damage_type: DamageType, power: int) -> Tuple[bool, str]:
        """Books generally resist zaps unless polymorphed or stone-to-flesh."""
        if damage_type == DamageType.POLYMORPH:
            return True, f"{self.id} shudders and changes!"
        return False, "Book is unaffected."

    def apply_inventory_action(self, action: str) -> bool:
        if action == "read":
            self.studied += 1
            self.learned = True
            return True
        return False

    def is_contained_in(self, container_id: str) -> bool:
        return self.container == container_id

    @property
    def charges(self) -> int: return self._charges
    @charges.setter
    def charges(self, val: int): self._charges = val


# ============================================================
# Spell Effects (Hybrid OOP: Class Attributes + Inheritance)
# ============================================================
class SpellEffect(EffectProtocol):
    """Base spell effect. Uses class attributes for fast O(1) type checks."""
    effect_type: str = "spell"
    damage_type: Optional[DamageType] = None
    power: int = 6
    duration: int = 0
    range: int = 7
    requires_direction: ClassVar[bool] = True
    is_immediate: ClassVar[bool] = False
    skill_bonus: ClassVar[bool] = False
    int_scaled: ClassVar[bool] = False
    is_novel: ClassVar[bool] = False

    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        return 0, f"{target.name} resists the spell."

    def apply_to_object(self, target: ObjectProtocol, world: WorldProtocol) -> Tuple[bool, str]:
        return False, "Spell doesn't affect objects."

    def apply_to_terrain(self, pos: Tuple[int, int], world: WorldProtocol) -> Dict[str, Any]:
        return {"affected": False}

    def calculate_damage(self, nd: int, caster_int: int) -> int:
        base = random.randint(1, 6) * min(nd, 6)
        if self.int_scaled:
            base += max(0, min(3, caster_int - 20))  # Simplified INT scaling
        if self.skill_bonus:
            base += random.randint(0, 2)
        return base


class DamageSpell(SpellEffect):
    requires_direction = True; is_immediate = False; int_scaled = True

    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        if target.resists(self.damage_type or DamageType.FIRE):
            return 0, f"{target.name} resists the {self.effect_type}!"
        return 0, f"{target.name} takes damage from {self.effect_type}."


class FireballEffect(DamageSpell):
    effect_type = "fireball"; damage_type = DamageType.FIRE
    requires_direction = False; is_immediate = True
    def apply_to_monster(self, target, world): return 0, f"{target.name} burns!"

class ConeOfColdEffect(DamageSpell):
    effect_type = "cone of cold"; damage_type = DamageType.COLD
    requires_direction = True

class LightningEffect(DamageSpell):
    effect_type = "lightning bolt"; damage_type = DamageType.LIGHTNING
    requires_direction = True

class MagicMissileEffect(DamageSpell):
    effect_type = "magic missile"; damage_type = DamageType.MAGIC_MISSILE
    requires_direction = True


class StatusSpell(SpellEffect):
    requires_direction = True

class SleepEffect(StatusSpell):
    effect_type = "sleep ray"; damage_type = DamageType.SLEEP
    def apply_to_monster(self, target, world):
        if not target.resists(self.damage_type):
            target.is_sleeping = True
            target.sleep_duration = 25
            return 0, f"{target.name} falls asleep!"
        return 0, f"{target.name} resists sleep!"

class PolymorphEffect(StatusSpell):
    effect_type = "polymorph"; damage_type = DamageType.POLYMORPH
    def apply_to_monster(self, target, world):
        if target.can_polymorph():
            return 0, f"{target.name} shudders and transforms!"
        return 0, f"{target.name} is unaffected!"

class CancellationEffect(StatusSpell):
    effect_type = "cancellation"; damage_type = DamageType.CANCELLATION
    def apply_to_monster(self, target, world):
        for item in target.inventory:
            if hasattr(item, 'charges') and item.charges > 0:
                item.charges = -1
        return 0, f"{target.name}'s magical items are cancelled!"

class TeleportEffect(StatusSpell):
    effect_type = "teleport"; damage_type = DamageType.TELEPORTATION
    def apply_to_monster(self, target, world):
        new_pos = (random.randint(0, 79), random.randint(0, 21))
        target.pos = new_pos
        return 0, f"{target.name} is teleported!"

class HealingEffect(StatusSpell):
    effect_type = "healing"; damage_type = DamageType.HEALING
    def apply_to_monster(self, target, world):
        heal = min(12, target.max_hp - target.hp)
        if heal > 0: target.hp += heal
        return heal, f"{target.name} feels better."

class DeathEffect(SpellEffect):
    effect_type = "finger of death"; damage_type = DamageType.DEATH
    requires_direction = True
    def apply_to_monster(self, target, world):
        if not target.resists(self.damage_type) and not target.is_nonliving:
            target.take_damage(target.max_hp, DamageType.DEATH)
            return 0, f"{target.name} is disintegrated!"
        return 0, f"{target.name} is unaffected."


# ============================================================
# Spell Actor (BaseActor + Casting Logic)
# ============================================================
class SpellActor(BaseActor):
    """Handles spell casting, skill checks, beam traversal, and book consumption.
    Maps directly to spell.c: cast(), make_spell(), spell_hit(), spells(), do_cast_spell()."""
    
    def __init__(self, world: WorldProtocol, router: MessageRouter):
        self.world = world
        self.router = router
        self.effect_map = {
            SpellType.MAGIC_MISSILE: MagicMissileEffect,
            SpellType.FIREBALL: FireballEffect,
            SpellType.CONE_OF_COLD: ConeOfColdEffect,
            SpellType.LIGHTNING: LightningEffect,
            SpellType.SLEEP: SleepEffect,
            SpellType.DEATH: DeathEffect,
            SpellType.POLYMORPH: PolymorphEffect,
            SpellType.CANCELLATION: CancellationEffect,
            SpellType.TELEPORT: TeleportEffect,
            SpellType.HEALING: HealingEffect,
        }

    def cast_spell(self, book: Spellbook, caster: MonsterProtocol, direction: Optional[tuple] = None) -> Tuple[int, str]:
        """Main entry point. Replaces spell.c:cast() and do_cast_spell()."""
        if book.charges <= 0:
            return 0, "The book has no charges."
        
        effect_cls = self.effect_map.get(book.spell_type)
        if not effect_cls:
            return 0, "Unknown spell in book."
        
        effect = effect_cls()
        
        # Direction check
        if effect.requires_direction and direction is None:
            return 0, "Must specify direction for this spell."
        
        # Consume charge
        book.charges -= 1
        if book.charges <= 0:
            book.charges = -1  # Mark as exhausted
        
        # Track spell learning
        self._track_learning(book, caster)
        
        # Execute effect
        if effect.is_immediate:
            return self._cast_immediate(effect, caster, world=self.world)
        else:
            return self._cast_beam(effect, direction or (0, 0), caster)

    def _cast_immediate(self, effect: SpellEffect, caster: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]:
        """Handles immediate spells (fireball, teleport, etc.)"""
        # Fireball hits caster if direction not specified
        targets = [caster]
        if effect.effect_type == "fireball":
            targets = world.get_monsters_at(caster.pos) + [caster]
        
        for target in targets:
            dmg, msg = effect.apply_to_monster(target, world)
            self.router.broadcast("spell_hit", {"target": target.id, "effect": effect.effect_type})
        return 0, f"{caster.name} casts {effect.effect_type}."

    def _cast_beam(self, effect: SpellEffect, direction: tuple, caster: MonsterProtocol) -> Tuple[int, str]:
        """Handles directional beam spells. Replaces spell.c:spells() + beam traversal."""
        beam = SpellBeam(effect, caster, direction, world=self.world, router=self.router)
        results = beam.traverse()
        
        # Aggregate results
        total_dmg = sum(r.get("damage", 0) for r in results if "damage" in r)
        if total_dmg > 0:
            return total_dmg, f"{caster.name} casts {effect.effect_type}."
        return 0, f"{caster.name} casts {effect.effect_type} (missed)."

    def _track_learning(self, book: Spellbook, caster: MonsterProtocol):
        """Replaces spell.c:learn_spell() / experience gain."""
        if book.is_novel:
            book.learned = True
            return
        if not book.learned and book.studied > 0:
            book.learned = True
            self.router.broadcast("spell_learned", {"book_id": book.id, "caster": caster.id})

    def _calculate_spell_damage(self, caster: MonsterProtocol, base_dmg: int) -> int:
        """Replaces spell.c:spell_damage_bonus(). Scales with INT & skill."""
        bonus = 0
        # Simplified skill/int scaling
        if caster.intelligence > 18: bonus = min(3, caster.intelligence - 18)
        return base_dmg + bonus

    # BaseActor interface implementations
    def _on_attack(self, msg: AttackMessage) -> Any:
        return {"error": "spell_actor_does_not_handle_attacks"}
    
    def _on_status(self, msg: StatusEffectMessage) -> Any:
        return {"error": "spell_actor_does_not_handle_status_messages"}
    
    def _on_terrain(self, msg: TerrainInteractionMessage) -> Any:
        return {"error": "spell_actor_does_not_handle_terrain_messages"}
    
    def _on_inventory(self, msg: InventoryUpdateMessage) -> Any:
        if msg["action"] == "read":
            book = self.world.get_actor(msg["item_id"])
            if isinstance(book, Spellbook):
                book.apply_inventory_action("read")
                return {"read": True, "learned": book.learned}
        return {"error": "invalid_inventory_action"}
    
    def _on_query(self, msg: QueryMessage) -> Any:
        if msg["query"] == "check_resistance":
            target = self.world.get_actor(msg["target_pid"])
            if isinstance(target, MonsterProtocol):
                return {"resists": target.resists(msg.get("damage_type", DamageType.FIRE))}
        return {"error": "unknown_query"}


# ============================================================
# Spell Beam (Transient Helper)
# ============================================================
class SpellBeam:
    """Transient process for directional beam spells. Queries world via contracts."""
    def __init__(self, effect: SpellEffect, caster: MonsterProtocol, 
                 direction: tuple, world: WorldProtocol, router: MessageRouter):
        self.effect = effect
        self.caster = caster
        self.dir = direction
        self.world = world
        self.router = router
        self.pos = caster.pos
        self.range = 7
        self.results: List[Dict] = []

    def traverse(self) -> List[Dict]:
        for step in range(self.range):
            self.pos = (self.pos[0] + self.dir[0], self.pos[1] + self.dir[1])
            
            # Query terrain
            terrain_resp = self.world.get_terrain_at(self.pos)
            if terrain_resp.get("blocked"):
                self._handle_bounce()
                continue
                
            # Query monsters
            monsters = self.world.get_monsters_at(self.pos)
            for monster in monsters:
                dmg, _ = self.effect.apply_to_monster(monster, self.world)
                self.results.append({"target": monster.id, "damage": dmg})
                self.router.broadcast("beam_hit", {"pos": self.pos, "monster": monster.id})
            
            # Check bounds/walls
            if not self._is_valid(self.pos):
                self._handle_bounce()
                
        return self.results

    def _is_valid(self, pos: tuple) -> bool:
        return 0 <= pos[0] < 80 and 0 <= pos[1] < 22

    def _handle_bounce(self):
        self.router.broadcast("beam_bounced", {"pos": self.pos, "dir": self.dir})
        self.dir = (-self.dir[0], -self.dir[1])


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
        def get_terrain_at(self, pos): return {"blocked": False}

    class MockRouter:
        def broadcast(self, msg_type, payload): pass

    world = MockWorld()
    router = MockRouter()
    spell_actor = SpellActor(world, router)

    # Mock monster with required attrs
    class TestMonster(MonsterProtocol):
        def __init__(self):
            self.id = "hero"; self.name = "Hero"; self.hp = 15; self.max_hp = 15
            self.ac = 10; self.pos = (10,10); self.alive = True
            self.is_sleeping = False; self.is_invisible = False
            self.is_undead = False; self.is_demon = False; self.is_golem = False
            self.is_nonliving = False; self.inventory = []
            self.intelligence = 16; self.confused = False
        def resists(self, dmg): return False
        def react_to_damage(self, dmg, power): return power, f"Hero takes {power} damage."
        def apply_status(self, effect, duration): return True
        def can_polymorph(self): return True
        def is_vulnerable_to(self, dmg): return True

    hero = TestMonster()
    world.register_actor("hero", hero)

    book = Spellbook(otype=ObjectType.BOOK, spell_type=SpellType.FIREBALL, charges=3)
    world.register_actor("book1", book)

    dmg, msg = spell_actor.cast_spell(book, hero, direction=(1, 0))
    print(f"Casted spell: {msg} | Book charges left: {book.charges}")

