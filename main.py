"""The imperative shell: a ~40-line game loop around the pure core.

    keys in   ->  read_command()
    command   ->  step(world, cmd, rng)
    events    ->  message log + screen
"""
from __future__ import annotations

import os
import random
from typing import List

from core import GameOverEvent, MessageEvent, step
from core.worldgen import new_world
from ui import read_command, render


def main() -> None:
    rng = random.Random(42)  # same seed as the old demo
    world = new_world(rng)
    log: List[str] = []

    print("🎮 PyHack — functional core, events out")
    print("   WASD/Arrows to move | g pick up | w<letter> wear | t<letter> take off | Q to quit")
    print("   > go down the stairs | < climb back up: the dungeon has 3")
    print("   levels; level 2+ generates on first visit and stays intact when")
    print("   you come back.  Reaching the bottom level wins!")
    print("   r<letter> read a scroll | z<letter> zap a wand | c<letter> cast a spell")
    print("   e<letter> eat a food (the demo floor carries an apple, an orange,")
    print("   a food ration and a melon -- pick them up with g first)")
    print("   (zaps and beam spells ask for the direction: n/s/e/w/ne/nw/se/sw)")
    print("   The floor scrolls (enchant weapon/armor, remove curse, "
          "teleportation, blank paper) are read with r<letter> -- the "
          "cursed cloak needs a remove curse scroll before it can come off.")
    print("   The floor wands (striking, cold) and books (magic missile, "
          "cone of cold, healing) are the zap-port demo kit: the wand of "
          "cold and the cone of cold book run the SAME effect (the shared "
          "zap registry).")
    print("   Bump into a monster to attack it!")
    print("   Traps trigger when you step on them (30% chance).")
    print("   The AC on the status line is the computed effective AC")
    print("   (base 10 - your worn gear; wear the floor armour!).")
    print("   Pw on the status line is spell power: casting a level-N book")
    print("   costs 5*N Pw, and it regens slowly (1 Pw every 37 turns at")
    print("   level 1).  Your hunger is on the status line too: the gauge")
    print("   drains 1/turn (900 at start); at 'Weak' you may faint, a")
    print("   fainted hero starves if not fed, and eating while 'Satiated'")
    print("   can choke you (choking is 19/20 fatal).  Too hungry (<= 10)")
    print("   you can't cast spells.")
    print("   The floor items wear their NetHack glyphs")
    print("   (defsym.h): ? scrolls, ) weapons, [ armour, + spell books,")
    print("   / wands.")
    print()

    while not world.over:
        os.system("cls" if os.name == "nt" else "clear")
        print(render(world, log))
        cmd = read_command(world)
        if cmd is None:
            break
        events = step(world, cmd, rng)
        for e in events:
            if isinstance(e, MessageEvent):
                log.append(e.text)
            elif isinstance(e, GameOverEvent):
                log.append(e.reason)

    os.system("cls" if os.name == "nt" else "clear")
    print(render(world, log))
    if not world.hero.alive:
        print("💀 HERO DEAD — Thanks for playing the NetHack demo!")
    else:
        print("🎉 ALL MONSTERS CLEARED! You survive the cave.")


if __name__ == "__main__":
    main()
