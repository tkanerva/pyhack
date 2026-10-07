# PyHack

An experimental NetHack port in Python, rebuilt around a
**functional core / events out** architecture.

The whole game simulation lives in `core/` and is pure: no I/O, no
global state, no message bus. One function advances the game; side
effects come back as data. See [ARCHITECTURE.md](ARCHITECTURE.md) for
the design rationale and the old-file → new-file mapping.

## Layout

```
core/            pure simulation (no I/O)
  types.py         World, Monster, Trap, Item, Map, all enums
  events.py        Event dataclasses (the "side effects out")
  commands.py      MoveCommand / WaitCommand / ZapCommand / ...
  rules.py         dice, resistances, apply_damage, status tickers
  traps.py         trap effect registry + trigger logic
  zap.py           wand beams
  potions.py       quaffing
  scrolls.py       the read.c subset (five seffect_* + STUBs)
  spells.py        spell beams / fireball
  worn.py          armor slots (owornmask) + the computed effective AC
  pickup.py        pick up the topmost item on your tile
  step.py          step(world, cmd, rng) -> [Event]   <- the heart
  worldgen.py      deterministic demo-cave construction
ui/              console rendering + key input (the only I/O)
main.py          ~40-line game loop gluing core to ui
tests/           pytest suite
```

## Run

```
python main.py
```

WASD / arrow keys to move, bump a monster to attack it, `g` to pick
up, `w<letter>` to wear and `t<letter>` to take off, `r<letter>` to
read a scroll (letters are the inventory letters on the screen), `q`
to quit.  The `AC` on the status line is the computed effective AC:
the hero starts at base 10 wearing chain mail (effective 5) -- go get
the floor armour.  The floor also carries the demo scrolls (enchant
weapon / enchant armor, remove curse, teleportation, blank paper);
the cursed floor cloak only comes off after a remove curse scroll.

## Test

```
pip install -r requirements-dev.txt
pytest            # run from the repo root
```

The tests are deterministic: the core takes an injected
`random.Random` (or any object with `randint`/`choice`), and `tests`
includes a `SeqRng` helper for exact roll-by-roll control.
