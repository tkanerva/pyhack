# contracts.py
"""
NetHack Hybrid OOP Contracts
Defines structural interfaces, message schemas, and actor routing primitives.
Each source module implements its own protocol and plugs into the world registry independently.
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable, TypedDict, Literal, Optional, Dict, Tuple, List, Any
from enum import Enum, auto
from abc import ABC, abstractmethod
from collections import defaultdict

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

class DamageType(Enum):
    MAGIC_MISSILE = auto()
    FIRE = auto()
    COLD = auto()
    SLEEP = auto()
    DEATH = auto()
    LIGHTNING = auto()
    POISON = auto()
    ACID = auto()
    CANCELLATION = auto()

class ObjectType(Enum):
    WAND = auto(); SCROLL = auto(); POTION = auto(); WEAPON = auto()
    ARMOR = auto(); TOOL = auto(); FOOD = auto(); CORPSE = auto()
    EGG = auto(); STATUE = auto(); RING = auto(); AMULET = auto()
    GEM = auto(); BOULDER = auto(); BOOK = auto()

class Direction(Enum):
    N = (0, -1); S = (0, 1); E = (1, 0); W = (-1, 0)
    NE = (1, -1); NW = (-1, -1); SE = (1, 1); SW = (-1, 1)
    UP = (0, 0, 1); DOWN = (0, 0, -1); NODIR = None

# ============================================================
# Message Schemas (TypedDict for serialization & type safety)
# ============================================================
class AttackMessage(TypedDict):
    type: Literal["attack"]
    damage_type: DamageType
    power: int
    source: str
    reflect: bool = False

class StatusEffectMessage(TypedDict):
    type: Literal["status"]
    effect: Literal["sleep", "slow", "haste", "teleport", "polymorph", "cancel", "invisibility"]
    duration: int
    target_pid: str

class TerrainInteractionMessage(TypedDict):
    type: Literal["terrain"]
    action: Literal["melt", "freeze", "evaporate", "break_door", "open_door", "reveal_secret"]
    pos: Tuple[int, int]
    source: str

class InventoryUpdateMessage(TypedDict):
    type: Literal["inventory"]
    action: Literal["add", "remove", "equip", "unequip", "drop", "pickup", "merge"]
    item_id: str
    to: Optional[str]
    from_: Optional[str] = None  # Fixed: 'from' is a reserved keyword in Python

class QueryMessage(TypedDict):
    type: Literal["query"]
    query: Literal["get_hp", "get_pos", "get_status", "list_inventory", "check_resistance"]
    target_pid: str

# ============================================================
# Domain Protocols (Structural Interfaces)
# ============================================================
@runtime_checkable
class MonsterProtocol(Protocol):
    id: str
    name: str
    hp: int; max_hp: int; ac: int
    pos: Tuple[int, int]
    alive: bool; is_sleeping: bool; is_invisible: bool
    is_undead: bool; is_demon: bool; is_golem: bool; is_nonliving: bool

    def resists(self, dmg: DamageType) -> bool: ...
    def react_to_damage(self, dmg: DamageType, power: int) -> Tuple[int, str]: ...
    def apply_status(self, effect: str, duration: int) -> bool: ...
    def can_polymorph(self) -> bool: ...
    def is_vulnerable_to(self, dmg: DamageType) -> bool: ...

@runtime_checkable
class ObjectProtocol(Protocol):
    id: str; otype: ObjectType
    charges: int; blessed: bool; cursed: bool
    pos: Tuple[int, int]; container: Optional[str]; carrier: Optional[str]

    def react_to_zap(self, damage_type: DamageType, power: int) -> Tuple[bool, str]: ...
    def apply_inventory_action(self, action: str) -> bool: ...
    def is_contained_in(self, container_id: str) -> bool: ...

@runtime_checkable
class TerrainProtocol(Protocol):
    def get_terrain_at(self, pos: Tuple[int, int]) -> Dict[str, Any]: ...
    def react_to_effect(self, effect: str, pos: Tuple[int, int]) -> Dict[str, Any]: ...
    def has_door_at(self, pos: Tuple[int, int]) -> bool: ...
    def has_trap_at(self, pos: Tuple[int, int]) -> bool: ...
    def has_object_at(self, pos: Tuple[int, int]) -> bool: ...

@runtime_checkable
class WorldProtocol(Protocol):
    def get_actor(self, pid: str) -> Any: ...
    def register_actor(self, pid: str, actor: Any) -> None: ...
    def broadcast(self, message: Any, exclude: Optional[List[str]] = None) -> None: ...
    def query(self, message: QueryMessage) -> Any: ...
    def get_monsters_at(self, pos: Tuple[int, int]) -> List[MonsterProtocol]: ...
    def get_objects_at(self, pos: Tuple[int, int]) -> List[ObjectProtocol]: ...

@runtime_checkable
class EffectProtocol(Protocol):
    """Base for wands, spells, breaths, traps."""
    effect_type: str
    damage_type: Optional[DamageType]
    power: int; duration: int; range: int

    def apply_to_monster(self, target: MonsterProtocol, world: WorldProtocol) -> Tuple[int, str]: ...
    def apply_to_object(self, target: ObjectProtocol, world: WorldProtocol) -> Tuple[bool, str]: ...
    def apply_to_terrain(self, pos: Tuple[int, int], world: WorldProtocol) -> Dict[str, Any]: ...

# ============================================================
# Actor Base & Message Router (Decoupled Communication)
# ============================================================
class BaseActor(ABC):
    """Minimal actor base that routes messages to domain handlers."""
    def handle_message(self, message: Any) -> Any:
        msg_type = message.get("type") if isinstance(message, dict) else None
        handlers = {
            "attack": self._on_attack, "status": self._on_status,
            "terrain": self._on_terrain, "inventory": self._on_inventory,
            "query": self._on_query,
        }.get(msg_type, self._on_unhandled)
        return handlers(message)

    def _on_unhandled(self, message: Any) -> Dict[str, Any]:
        return {"error": "unhandled_message", "type": type(message)}

    @abstractmethod
    def _on_attack(self, msg: AttackMessage) -> Any: ...
    @abstractmethod
    def _on_status(self, msg: StatusEffectMessage) -> Any: ...
    @abstractmethod
    def _on_terrain(self, msg: TerrainInteractionMessage) -> Any: ...
    @abstractmethod
    def _on_inventory(self, msg: InventoryUpdateMessage) -> Any: ...
    @abstractmethod
    def _on_query(self, msg: QueryMessage) -> Any: ...

class MessageRouter:
    """Decoupled pub/sub routing. Replaces direct function calls."""
    def __init__(self, world: Optional[WorldProtocol] = None):
        # Store optional world reference to forward broadcasts
        self.world = world
        self._handlers: Dict[str, Dict[str, callable]] = defaultdict(dict)
        self._listeners: Dict[str, List[callable]] = defaultdict(list)

    def register(self, actor_id: str, msg_type: str, handler: callable):
        self._handlers[actor_id][msg_type] = handler

    def route(self, actor_id: str, message: Any) -> Any:
        handlers = self._handlers.get(actor_id, {})
        msg_type = message.get("type") if isinstance(message, dict) else None
        handler = handlers.get(msg_type, lambda m: {"error": "no_handler", "type": msg_type})
        return handler(message)

    def subscribe(self, msg_type: str, listener: callable):
        self._listeners[msg_type].append(listener)

    def broadcast(self, msg_type: str, payload: Any):
        # Forward to world if attached
        if self.world:
            self.world.broadcast(msg_type, payload)
        
        # Notify listeners
        for listener in self._listeners.get(msg_type, []):
            listener(payload)

