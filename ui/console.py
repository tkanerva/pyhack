"""Console front-end: the only I/O in the program.

render() turns World + log lines into text; read_command() turns a key
press into a Command.  Nothing in core/ imports anything from ui/ --
the dependency points one way only.
"""
from __future__ import annotations

from typing import List, Optional

from core import display
from core.commands import (CastCommand, CloseCommand, Command, EatCommand,
                           MoveCommand, PickupCommand, QuaffCommand,
                           ReadCommand, StairsCommand, TakeOffCommand,
                           WaitCommand, WearCommand, ZapCommand)
from core.hunger import HU_STAT
from core.items import wielded_of
from core.objects import DEF_OC_SYMS, ObjClass
from core.spells import SPELL_ZAPS
from core.types import Direction, HungerState, ObjectType, World
from core.vision import can_see
from core.worn import W_ACCESSORY, W_ARMOR, uac

# The old code lower-cased the key before comparing against "\x1b[A",
# so arrow keys never matched.  Compare lowercase consistently now.
ARROWS = {
    "w": (0, -1), "\x1b[a": (0, -1),
    "s": (0, 1), "\x1b[b": (0, 1),
    "a": (-1, 0), "\x1b[d": (-1, 0),
    "d": (1, 0), "\x1b[c": (1, 0),
}

# The zap direction prompt (C: getdir for the ray wands / spells)
DIRECTIONS = {
    "n": Direction.N, "s": Direction.S, "e": Direction.E, "w": Direction.W,
    "ne": Direction.NE, "nw": Direction.NW, "se": Direction.SE,
    "sw": Direction.SW,
}


def _ask_direction() -> Direction:
    key = input("Direction (n/s/e/w/ne/nw/se/sw): ").strip().lower()
    return DIRECTIONS.get(key, Direction.E)


def _item_by_letter(world: World, letter: str) -> Optional[str]:
    """The inventory item of the hero carrying `letter`, or None
    (C: the obj_to_let() lookup getobj() does).

    The letter is the item's own ``Item.invlet`` -- assigned once by
    core.invent.assigninvlet and kept while the item is held (C:
    flags.invlet_constant) -- not an index into the inventory list, so
    dropping or picking up an item never re-letters anything else
    (PLAN-INVENT.md §2.2 defect 1).
    """
    for it in world.hero.inventory:
        if it.invlet == letter:
            return it.id
    return None


def read_command(world: World, prompt: str = "Move: ") -> Optional[Command]:
    """Returns None to quit.

    Keys: WASD / arrows to move, `g` to pick up, `w<letter>` to wear,
    `t<letter>` to take off, `r<letter>` to read a scroll, `z<letter>`
    to zap a wand (+ the direction prompt), `c<letter>` to cast a
    spell (the direction prompt only for the beam spells -- the
    self spells cast at once), `e<letter>` to eat a food, `q<letter>`
    to quaff a potion (C: the lowercase 'q'; capital `Q` quits -- the
    demo's old case-insensitive quit is now the capital only),
    `x<n/s/e/w>` to close the door one step away (C: doclose -- 'c'
    already casts, so close moved to 'x'; a lone `x` is a wait) (the
    letters are the inventory letters shown in the screen's inventory
    line), `>` to go down the stairs / `<` to climb up (C: the '>' / '<'
    commands); anything else is a wait.
    """
    if world.occupation is not None:
        # C: while an occupation runs the bottom line shows the
        # occupation text and key input is queued (the occupation
        # consumes the turn) -- any key is a wait
        input(f"You are {world.occupation.text}... (any key waits): ")
        return WaitCommand()
    raw = input(prompt).strip()
    # C: 'Q' (capital) quits; lowercase 'q' is the quaff command
    if raw == "Q":
        return None
    key = raw.lower()
    if key == "g":
        return PickupCommand()
    # the stair commands (C: '>' -> dodown, '<' -> doup); input().lower()
    # leaves both glyphs alone
    if key == ">":
        return StairsCommand(up=False)
    if key == "<":
        return StairsCommand(up=True)
    # the close command (C: doclose, one step in a direction): 'x' +
    # an axis letter ('c' already casts, so close moved to 'x'); a
    # lone 'x' is a wait, like a lone 'q'
    if key.startswith("x") and len(key) == 2 and key[1] in "nsew":
        dx, dy = {"n": (0, -1), "s": (0, 1),
                  "e": (1, 0), "w": (-1, 0)}[key[1]]
        return CloseCommand(dx, dy)
    if len(key) == 2 and key[1].isalpha():
        item_id = _item_by_letter(world, key[1])
        if item_id is not None:
            if key[0] == "w":
                return WearCommand(item_id)
            if key[0] == "t":
                return TakeOffCommand(item_id)
            if key[0] == "r":
                return ReadCommand(item_id)
            if key[0] == "z":
                item = world.items[item_id]
                if (item.otype == ObjectType.WAND
                        and item.wand_type is not None):
                    return ZapCommand(item.wand_type, _ask_direction())
                return WaitCommand()
            if key[0] == "c":
                item = world.items[item_id]
                if (item.otype == ObjectType.BOOK
                        and item.spell_type is not None):
                    direction = (_ask_direction()
                                 if item.spell_type in SPELL_ZAPS
                                 else None)
                    return CastCommand(item_id, direction)
                return WaitCommand()
            if key[0] == "e":
                return EatCommand(item_id)
            if key[0] == "q":
                item = world.items[item_id]
                if (item.otype == ObjectType.POTION
                        and item.potion_type is not None):
                    return QuaffCommand(item_id)
                return WaitCommand()
            return WaitCommand()
    if key in ARROWS:
        dx, dy = ARROWS[key]
        return MoveCommand(dx, dy)
    return WaitCommand()


def _inventory_line(world: World) -> str:
    """The inventory line: carried items with their own inventory
    letter (``Item.invlet``, C: obj->invlet), worn items marked *worn*
    (the AC of the worn gear is on the status line above)."""
    inv = world.hero.inventory
    if not inv:
        return "🎒 (empty)"
    parts = []
    for it in inv:
        letter = it.invlet
        if it.owornmask & (W_ARMOR | W_ACCESSORY):
            parts.append(f"[{letter}: {it.name} *worn*]")
        else:
            parts.append(f"[{letter}: {it.name}]")
    return "🎒 " + " ".join(parts)


def render(world: World, log: List[str]) -> str:
    """Draw the screen.

    The map half is C's display layer: `display.docrt()` refreshes what
    the hero remembers of the level from the current view (C: the
    window port calls docrt() before a redraw), and then every square
    is painted from `Tile.glyph` -- the *memory*.  A square the hero
    has never seen is GLYPH_UNEXPLORED and draws blank, a wall is only
    a wall once it has been seen, and a corridor stays '#' after the
    hero walked past it.  Monsters float above the map and are never
    remembered (C: display_monster), so they are overlaid live, and
    only while the hero can see them.
    """
    display.docrt(world)
    lines: List[str] = []
    lines.append(f"🗺️  Level {world.lev} of {world.max_lev}")
    # the glyphs are the defsym.h symbols themselves (core.glyph): '|'
    # and '-' are the walls, '#' a corridor, '+' a closed door ('|' and
    # '-' again for an open one), '.' a lit floor, and a blank an
    # unexplored square
    lines.append("   @ = Hero | M = Monster | ^ = Seen Trap | X = Triggered Trap | | - = Wall or open door | # = Corridor | + = Closed door | . = Lit floor | > = Stairs down | < = Stairs up | blank = Unexplored")
    # the floor-glyph legend: the glyphs come from the same defsym.h
    # table the map uses (def_oc_syms, core.objects); the labels are
    # the classes the demo floor carries
    lines.append("   " + " | ".join(
        f"{DEF_OC_SYMS[oc].sym} = {label}"
        for oc, label in ((ObjClass.SCROLL, "Scroll"),
                          (ObjClass.WEAPON, "Weapon"),
                          (ObjClass.ARMOR, "Armour"),
                          (ObjClass.SPBOOK, "Spell Book"),
                          (ObjClass.WAND, "Wand"),
                          (ObjClass.FOOD, "Food"),
                          (ObjClass.POTION, "Potion"))))
    lines.append("")

    hero_pos = world.hero.pos
    # monsters are drawn live, on top of the memory (C: see_monsters()
    # floats them above the map; they are never part of levl[].glyph)
    monster_pos = {m.pos for m in world.actors.values()
                   if not m.is_hero and display.mon_visible(world, m)}
    # a trap going off is a transient effect, so it is drawn live too --
    # a *known* trap is part of the memory ('^', written by
    # display.map_trap)
    triggered = {t.pos for t in world.traps.values()
                 if t.triggered and t.lev == world.lev}

    for y in range(world.map.height):
        row = []
        for x in range(world.map.width):
            pos = (x, y)
            if pos == hero_pos:
                row.append("@")
            elif pos in monster_pos:
                row.append("M")
            elif pos in triggered and can_see(world, pos):
                row.append("X")
            else:
                # the hero's memory of the square: the terrain, a
                # remembered object, a known trap -- or blank when the
                # square has never been seen
                row.append(display.glyph_to_char(
                    world.map.tile_at(pos).glyph))
        lines.append("".join(row))

    hero = world.hero
    weapon = wielded_of(world, hero.id)
    weapon_name = weapon.name if weapon is not None else "bare hands"
    # the hunger text on the bottom line (C: the hu_stat[] table of
    # eat.c, printed by botl.c when uhs != NOT_HUNGRY)
    hu = (" | 🍖 " + HU_STAT[int(hero.uhs)].strip()
          if hero.uhs != HungerState.NOT_HUNGRY else "")
    # the running occupation text (C: the go.occtxt bottom line)
    occ = (" | 🍽️ " + world.occupation.text
           if world.occupation is not None else "")
    # the effective AC is the computed core.worn.uac (base - worn gear);
    # the experience level + XP (C: the botl u.uexp / the level in the
    # hero name field -- the demo shows both, always on, like the rest of
    # the status line; PLAN-EXPERIENCE.md decision 8)
    lines.append(f"🩸 HP: {hero.hp}/{hero.max_hp} | ⭐ Lvl: {hero.ulevel} | 📈 XP: {hero.uexp} | ⚡ Pw: {hero.uen}/{hero.uenmax} | 🛡️ AC: {uac(world, hero)} | ⚔️ {weapon_name} | 💥 Damage Taken: {hero.max_hp - hero.hp}{hu}{occ}")
    lines.append(_inventory_line(world))
    lines.append("")
    lines.append("📜 Log:")
    if log:
        for msg in log[-10:]:
            lines.append(f"   {msg}")
    else:
        lines.append("   No events yet.")
    return "\n".join(lines)
