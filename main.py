"""The imperative shell: a ~40-line game loop around the pure core.

    keys in   ->  read_command()
    command   ->  step(world, cmd, rng)
    events    ->  message log + screen
"""
from __future__ import annotations

import os
import random
import sys
from typing import List, Union

from core import GameOverEvent, ListCommand, MessageEvent, step
from core.calendar import midnight
from core.rnd import Rng
from core.worldgen import CAVERN, DEMO, MKLEV, new_world
from ui import inventory_lines, read_command, render

# The seed of the game (the old demo's 42).
SEED = 42


def make_rng(generator: str) -> Union[random.Random, Rng]:
    """The game rng a world made by `generator` runs on.

    Two streams, and the choice is the generator's:

    - the pinned demo cave keeps ``random.Random(42)``, the stream every
      earlier wave's expectations were recorded on;
    - the generated levels (``--mklev`` / ``--cavern``) draw through the
      ported C RNG -- ``rn2`` / ``rnd`` / ``rn1`` / ``rnl`` / ``d`` /
      ``rne``, which ``random.Random`` does not have (PLAN-MKLEV.md
      decision 8) -- so they run on ``core.rnd.Rng``; it also exposes
      ``randint`` / ``choice`` / ``shuffle``, so the whole runtime
      (step, the monster AI, the combat dice) works on it unchanged.

    Seeded from the same number, so a generated game is as reproducible
    as the demo's: the same seed draws the same level.
    """
    if generator == DEMO:
        return random.Random(SEED)
    return Rng(b"pyhack:%d" % SEED)


def main() -> None:
    # the level generator (WAVE3.md): --mklev / --cavern, the default
    # is the pinned demo cave; the rng follows the generator
    generator = MKLEV if "--mklev" in sys.argv else (
        CAVERN if "--cavern" in sys.argv else DEMO)
    rng = make_rng(generator)
    # the wall clock enters the game exactly here (C: midnight());
    # World.midnight stays fixed for the whole game (deterministic step)
    world = new_world(rng, midnight=midnight(), generator=generator)
    log: List[str] = []

    print("🎮 PyHack — functional core, events out")
    print("   (start with --mklev or --cavern for a generated level: rooms")
    print("   and corridors with doors, or a cavern)")
    print("   WASD/Arrows to move | g pick up | w<letter> wear | t<letter> take off | q<letter> quaff | x<n/s/e/w> close door | Q to quit")
    print("   > go down the stairs | < climb back up: the dungeon has 3")
    print("   levels; level 2+ generates on first visit and stays intact when")
    print("   you come back.  Reaching the bottom level wins!")
    print("   r<letter> read a scroll | z<letter> zap a wand | c<letter> cast a spell")
    print("   The floor carries a healing potion: pick it up (g) and")
    print("   drink it with q<letter>.  Capital Q still quits.")
    print("   i lists everything you carry (C: ddoinv); a class glyph")
    print("   lists just that class: ) weapons, [ armour, \" amulets,")
    print("   = rings, ( tools.  * shows what you wear and wield, and $")
    print("   your wallet.  A listing costs no turn.")
    print("   Every carried item keeps its own letter (C: invlet_constant):")
    print("   picking up or dropping one never re-letters the rest of the pack.")
    print("   e<letter> eat a food (the demo floor carries an apple, an orange,")
    print("   a food ration and a melon -- pick them up with g first).  The big")
    print("   foods are a multi-turn meal (a food ration: 5 turns, first bite")
    print("   instant): a monster that comes near interrupts it, and eating")
    print("   the same item again resumes where you left off.")
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
    print("   The map is your memory: a square you have not seen is blank,")
    print("   a wall is | or - only once you have looked at it, a corridor")
    print("   you walked down stays #, and monsters show only while you can")
    print("   see them (the floor glyphs you have seen are remembered).")
    print()

    while not world.over:
        os.system("cls" if os.name == "nt" else "clear")
        print(render(world, log))
        cmd = read_command(world)
        if cmd is None:
            break
        if isinstance(cmd, ListCommand):
            # a listing is a RENDER, not a turn (C: ddoinv & co. return
            # ECMD_OK): the console answers it from the world, the player
            # reads it at leisure, and the loop redraws -- step() is
            # never called, so the clock does not advance
            print()
            for line in inventory_lines(world, cmd.what):
                print("   " + line)
            input("   (press Enter) ")
            continue
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
