# game.py
"""
NetHack Demo Game v2
Adds monsters (Goblins, Orcs, Bats) that move, trigger traps, and attack.
Fully contract-compliant. No global state.
"""
from __future__ import annotations
import os
import random
from typing import Dict, List, Tuple, Any

from contracts import MonsterProtocol, ObjectProtocol, WorldProtocol, MessageRouter, QueryMessage
from trap import TrapActor, Trap, TrapType
from player import Hero
from monster import SimpleMonster, Goblin, Orc, Bat


class DemoWorld(WorldProtocol):
    def __init__(self):
        self.actors: Dict[str, Any] = {}
        self.traps: List[Trap] = []
        self.monsters: List[SimpleMonster] = []
        self.map: List[List[int]] = []
        self.trap_actor: TrapActor = TrapActor(self, MessageRouter())
        self.broadcast_messages: List[str] = []  # NEW: Listens to broadcasts

    def register_actor(self, pid: str, actor: Any) -> None:
        self.actors[pid] = actor

    def get_actor(self, pid: str) -> Any:
        return self.actors.get(pid)

    def broadcast(self, message: Any, exclude: List[str] | None = None) -> None:
        # NEW: Log broadcast messages for debugging
        if isinstance(message, str):
            self.broadcast_messages.append(message)
        else:
            self.broadcast_messages.append(str(message))

    def query(self, message: QueryMessage) -> Any: return None

    def get_monsters_at(self, pos: Tuple[int, int]) -> List[MonsterProtocol]:
        return [a for a in self.monsters + [self.actors.get('player')] if isinstance(a, MonsterProtocol) and a.pos == pos]

    def get_objects_at(self, pos: Tuple[int, int]) -> List[ObjectProtocol]:
        return [a for a in self.actors.values() if isinstance(a, ObjectProtocol) and a.pos == pos]

    def generate_map(self, width: int = 40, height: int = 20):
        self.map = [[1 if y == 0 or y == height-1 or x == 0 or x == width-1 else 0 for x in range(width)] for y in range(height)]
        for _ in range(15):
            wx, wy = random.randint(5, width-6), random.randint(5, height-6)
            self.map[wy][wx] = 1

    def place_traps(self, count: int = 8):
        floor_tiles = [(x, y) for y in range(len(self.map)) for x in range(len(self.map[0])) if self.map[y][x] == 0]
        for _ in range(min(count, len(floor_tiles))):
            if floor_tiles:
                x, y = random.choice(floor_tiles)
                floor_tiles.remove((x, y))
                trap = Trap(id=f"trap_{len(self.traps)}", trap_type=random.choice([
                    TrapType.PIT, TrapType.SPIKED_PIT, TrapType.FIRE_TRAP, TrapType.ARROW_TRAP
                ]), pos=(x, y), seen=False, triggered=False, disarmed=False)
                self.traps.append(trap)
                self.trap_actor.add_trap(trap)

    def spawn_monsters(self, goblins=4, orcs=2, bats=3):
        floor_tiles = [(x, y) for y in range(len(self.map)) for x in range(len(self.map[0])) if self.map[y][x] == 0]
        random.shuffle(floor_tiles)
        for i in range(goblins):
            if floor_tiles:
                g = Goblin(floor_tiles.pop())
                self.monsters.append(g)
                self.actors[f"goblin_{i}"] = g
        for i in range(orcs):
            if floor_tiles:
                o = Orc(floor_tiles.pop())
                self.monsters.append(o)
                self.actors[f"orc_{i}"] = o
        for i in range(bats):
            if floor_tiles:
                b = Bat(floor_tiles.pop())
                self.monsters.append(b)
                self.actors[f"bat_{i}"] = b


def render(map_data: List[List[int]], hero: Hero, monsters: List[SimpleMonster], traps: List[Trap], messages: List[str], broadcasts: List[str]):
    # Print broadcasts as the very first line after clearing screen
    if broadcasts:
        print("📡 Broadcasts:")
        for b in broadcasts:
            print(f"   {b}")
        print("-" * 40)
        
    print("🗺️  Cave Map")
    print("   @ = Hero | M/O/B = Monster | ^ = Seen Trap | # = Wall | X = Triggered Trap")
    print()
    for y, row in enumerate(map_data):
        line = ""
        for x, tile in enumerate(row):
            if (x, y) == hero.pos:
                line += "@"
            elif any(m.pos == (x, y) for m in monsters):
                line += "M"
            elif (x, y) in [(t.pos for t in traps if t.triggered)]:
                line += "X"
            elif (x, y) in [(t.pos for t in traps if t.seen)]:
                line += "^"
            elif tile == 1:
                line += "#"
            else:
                line += " "
        print(line)

    print()
    print("📜 Log:")
    for msg in messages:
        print(f"   {msg}")
    if not messages:
        print("   No events yet.")
    print()


def main():
    random.seed(42)
    os.system('cls' if os.name == 'nt' else 'clear')

    world = DemoWorld()
    world.generate_map(width=40, height=20)
    world.place_traps(count=10)
    world.spawn_monsters(goblins=4, orcs=2, bats=3)

    hero = Hero(pos=(20, 10), hp=25)
    world.actors["player"] = hero

    print("🎮 NetHack OOP Demo v3 (Fixed)")
    print("   WASD/Arrows to move | Q to quit")
    print("   Monsters trigger traps & attack if adjacent!")
    print("   Die from 10+ damage total.")
    print()

    all_messages: List[str] = []

    while hero.alive and any(m.alive for m in world.monsters):
        os.system('cls' if os.name == 'nt' else 'clear')
        render(world.map, hero, world.monsters, world.traps, all_messages[-5:])
        print(f"🩸 HP: {hero.hp}/{hero.max_hp} | 💥 Damage Taken: {25 - hero.hp}")
        print("   [WASD/Arrows to move, Q to quit]")

        key = input("   Move: ").strip().lower()
        dx, dy = 0, 0
        if key in ("w", "up", "\x1b[A"): dy = -1
        elif key in ("s", "down", "\x1b[B"): dy = 1
        elif key in ("a", "left", "\x1b[D"): dx = -1
        elif key in ("d", "right", "\x1b[C"): dx = 1
        elif key == "q": break

        # 1. Player move + trap check
        if hero.move(dx, dy, world.map):
            hero.check_and_trigger_traps(world)
            if hero.last_messages:
                all_messages.append(hero.last_messages[-1])

        # 2. Monster turns
        for mon in world.monsters:
            if not mon.alive: continue
            
            # FIX: Always check for traps, even if monster didn't move
            moved = mon.move(world.map)
            mon.check_and_trigger_traps(world)
            
            if mon.last_messages:
                all_messages.append(mon.last_messages[-1])

            # 3. Combat if adjacent
            if abs(mon.pos[0] - hero.pos[0]) + abs(mon.pos[1] - hero.pos[1]) == 1:
                dmg = mon.attack(hero)
                if dmg > 0:
                    all_messages.append(f"⚔️ {mon.name} hits you for {dmg} damage!")
                else:
                    all_messages.append(f"🛡️ {mon.name} misses you.")

        # 4. Cleanup & Limit messages
        world.monsters = [m for m in world.monsters if m.alive]
        all_messages = all_messages[-10:]

    if not hero.alive:
        os.system('cls' if os.name == 'nt' else 'clear')
        render(world.map, hero, world.monsters, world.traps, all_messages[-5:], world.broadcast_messages[-10:])
        print(f"\n💀 HERO DEAD | Total Damage Taken: {25 - hero.hp}")
        print("   Thanks for playing the NetHack OOP Demo!")
    elif not any(m.alive for m in world.monsters):
        print("\n🎉 ALL MONSTERS CLEARED! You survive the cave.")


if __name__ == "__main__":
    main()

