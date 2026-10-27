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
  stairs.py        the stairs system: '>' / '<', the level transition
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
to quit.  `>` goes down the stairs, `<` climbs back up: the dungeon
has 3 levels, level 2+ generates on first visit and stays intact when
you come back, and reaching the bottom level wins.  The `AC` on the
status line is the computed effective AC: the hero starts at base 10
wearing chain mail (effective 5) -- go get the floor armour.  `Pw` is
spell power: casting a level-N book costs 5*N Pw, and it regens
slowly.  The floor items wear their NetHack glyphs (the defsym.h
object-class table) -- `?` scrolls, `)` weapons, `[` armour, `+`
spell books, `/` wands, `>` / `<` the stairs.  The floor also carries
the demo scrolls (enchant weapon /
enchant armor, remove curse, teleportation, blank paper); the cursed
floor cloak only comes off after a remove curse scroll.

## Test

```
pip install -r requirements-dev.txt
pytest            # run from the repo root
```

The tests are deterministic: the core takes an injected
`random.Random` (or any object with `randint`/`choice`), and `tests`
includes a `SeqRng` helper for exact roll-by-roll control.

## Type check

```
pip install -r requirements-dev.txt
mypy              # run from the repo root; reads mypy.ini
```

`mypy.ini` pins what a bare `mypy` checks (`core`, `ui`, `tests`,
`main.py`, `conftest.py`) and stays at mypy's defaults on purpose: the
port is typed only as far as the C transcription allows, so the strict
flags are switched on one at a time as the error count reaches zero
(the list is at the bottom of the file).

The C tables -- `core/objects*.py` and `core/monst*.py` -- are split
by role: the declarations (`*_defs.py`: the enums, the constants, the
row types and the row-macro builders), the table data (`*_data.py`)
and the public API (`objects.py` / `monst.py`, which adds the derived
indices and accessors).  That one-way chain (`*_data` -> `*_defs`,
api -> both) is what keeps the C-style integer constants plain and
annotation-free: with the declarations and the table in one module the
two import each other, and a type checker cannot determine the type of
a constant read from a module it is still analysing.

The one member of that family with a module of its own is
`core/objects_enum.py`: the 480-member `ObjType` enum (C:
OBJECTS_ENUM).  It is a literal class body -- one member per line, C
order, `auto()` values -- because that is the only form a type checker
can read the members from.  Built with the functional API from a name
table the members exist only at run time, so `ObjType.DAGGER` would be
an error at every one of its ~280 uses, and no annotation on the use
sites can help.  The count now stands at zero.

