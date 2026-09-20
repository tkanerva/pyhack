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
    print("   WASD/Arrows to move | Q to quit")
    print("   Bump into a monster to attack it!")
    print("   Traps trigger when you step on them (30% chance).")
    print()

    while not world.over:
        os.system("cls" if os.name == "nt" else "clear")
        print(render(world, log))
        cmd = read_command()
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
