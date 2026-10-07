"""Console front-end: the only I/O in the program.

render() turns World + log lines into text; read_command() turns a key
press into a Command.  Nothing in core/ imports anything from ui/ --
the dependency points one way only.
"""
from __future__ import annotations

from typing import List, Optional

from core.commands import (Command, MoveCommand, PickupCommand,
                           ReadCommand, TakeOffCommand, WaitCommand,
                           WearCommand)
from core.items import wielded_of
from core.types import Item, Pos, World
from core.worn import W_ACCESSORY, W_ARMOR, uac

# The old code lower-cased the key before comparing against "\x1b[A",
# so arrow keys never matched.  Compare lowercase consistently now.
ARROWS = {
    "w": (0, -1), "\x1b[a": (0, -1),
    "s": (0, 1), "\x1b[b": (0, 1),
    "a": (-1, 0), "\x1b[d": (-1, 0),
    "d": (1, 0), "\x1b[c": (1, 0),
}


def _item_by_letter(world: World, letter: str) -> Optional[str]:
    """The inventory item of the hero carrying letter `a`, `b`, ...
    (inventory order), or None."""
    inv = world.hero.inventory
    idx = ord(letter) - ord("a")
    if 0 <= idx < len(inv):
        return inv[idx].id
    return None


def read_command(world: World, prompt: str = "Move: ") -> Optional[Command]:
    """Returns None to quit.

    Keys: WASD / arrows to move, `g` to pick up, `w<letter>` to wear,
    `t<letter>` to take off, `r<letter>` to read a scroll (the letters
    are the inventory letters shown in the screen's inventory line),
    `q` to quit; anything else is a wait.
    """
    key = input(prompt).strip().lower()
    if key == "q":
        return None
    if key == "g":
        return PickupCommand()
    if len(key) == 2 and key[0] in ("w", "t", "r") and key[1].isalpha():
        item_id = _item_by_letter(world, key[1])
        if item_id is not None:
            if key[0] == "w":
                return WearCommand(item_id)
            if key[0] == "t":
                return TakeOffCommand(item_id)
            return ReadCommand(item_id)
    if key in ARROWS:
        dx, dy = ARROWS[key]
        return MoveCommand(dx, dy)
    return WaitCommand()


def _inventory_line(world: World) -> str:
    """The inventory line: carried items with their letter in
    inventory order, worn items marked *worn* (the AC of the worn gear
    is on the status line above)."""
    inv = world.hero.inventory
    if not inv:
        return "🎒 (empty)"
    parts = []
    for i, it in enumerate(inv):
        letter = chr(ord("a") + i)
        if it.owornmask & (W_ARMOR | W_ACCESSORY):
            parts.append(f"[{letter}: {it.name} *worn*]")
        else:
            parts.append(f"[{letter}: {it.name}]")
    return "🎒 " + " ".join(parts)


def render(world: World, log: List[str]) -> str:
    lines: List[str] = []
    lines.append("🗺️  Cave Map")
    lines.append("   @ = Hero | M = Monster | ^ = Seen Trap | X = Triggered Trap | # = Wall | ! = Scroll")
    lines.append("")

    hero_pos = world.hero.pos
    monster_pos = {m.pos for m in world.actors.values() if not m.is_hero and m.alive}
    triggered = {t.pos for t in world.traps.values() if t.triggered}
    seen = {t.pos for t in world.traps.values() if t.seen and not t.triggered}

    # Collect items on the floor (not carried by a monster)
    floor_items: dict[Pos, List[Item]] = {}
    for item in world.items.values():
        if item.pos is not None and item.container is None:
            floor_items.setdefault(item.pos, []).append(item)

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
            elif pos in floor_items:
                # Display scrolls with "!" (any scroll type)
                for item in floor_items[pos]:
                    if item.otype.name == "SCROLL":
                        row.append("!")
                        break
                else:
                    row.append(".")  # other floor items
            else:
                row.append(" ")
        lines.append("".join(row))

    hero = world.hero
    weapon = wielded_of(world, hero.id)
    weapon_name = weapon.name if weapon is not None else "bare hands"
    # the effective AC is the computed core.worn.uac (base - worn gear)
    lines.append(f"🩸 HP: {hero.hp}/{hero.max_hp} | 🛡️ AC: {uac(world, hero)} | ⚔️ {weapon_name} | 💥 Damage Taken: {hero.max_hp - hero.hp}")
    lines.append(_inventory_line(world))
    lines.append("")
    lines.append("📜 Log:")
    if log:
        for msg in log[-10:]:
            lines.append(f"   {msg}")
    else:
        lines.append("   No events yet.")
    return "\n".join(lines)
