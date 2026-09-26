"""Console front-end: the only I/O in the program.

render() turns World + log lines into text; read_command() turns a key
press into a Command.  Nothing in core/ imports anything from ui/ --
the dependency points one way only.
"""
from __future__ import annotations

from typing import List, Optional

from core.commands import Command, MoveCommand, WaitCommand
from core.items import wielded_of
from core.types import World

# The old code lower-cased the key before comparing against "\x1b[A",
# so arrow keys never matched.  Compare lowercase consistently now.
ARROWS = {
    "w": (0, -1), "\x1b[a": (0, -1),
    "s": (0, 1), "\x1b[b": (0, 1),
    "a": (-1, 0), "\x1b[d": (-1, 0),
    "d": (1, 0), "\x1b[c": (1, 0),
}


def read_command(prompt: str = "Move: ") -> Optional[Command]:
    """Returns None to quit."""
    key = input(prompt).strip().lower()
    if key == "q":
        return None
    if key in ARROWS:
        dx, dy = ARROWS[key]
        return MoveCommand(dx, dy)
    return WaitCommand()


def render(world: World, log: List[str]) -> str:
    lines: List[str] = []
    lines.append("🗺️  Cave Map")
    lines.append("   @ = Hero | M = Monster | ^ = Seen Trap | X = Triggered Trap | # = Wall")
    lines.append("")

    hero_pos = world.hero.pos
    monster_pos = {m.pos for m in world.actors.values() if not m.is_hero and m.alive}
    triggered = {t.pos for t in world.traps.values() if t.triggered}
    seen = {t.pos for t in world.traps.values() if t.seen and not t.triggered}

    for y in range(world.map.height):
        row = []
        for x in range(world.map.width):
            pos = (x, y)
            if pos == hero_pos:
                row.append("@")
            elif pos in monster_pos:
                row.append("M")
            elif pos in triggered:
                row.append("X")
            elif pos in seen:
                row.append("^")
            elif world.map.is_wall(pos):
                row.append("#")
            else:
                row.append(" ")
        lines.append("".join(row))

    hero = world.hero
    weapon = wielded_of(world, hero.id)
    weapon_name = weapon.name if weapon is not None else "bare hands"
    lines.append("")
    lines.append(f"🩸 HP: {hero.hp}/{hero.max_hp} | ⚔️ {weapon_name} | 💥 Damage Taken: {hero.max_hp - hero.hp}")
    lines.append("")
    lines.append("📜 Log:")
    if log:
        for msg in log[-10:]:
            lines.append(f"   {msg}")
    else:
        lines.append("   No events yet.")
    return "\n".join(lines)
