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
  types.py         World, Monster, Trap, Item, Map, Stairway, all enums
  events.py        Event dataclasses (the "side effects out")
  commands.py      MoveCommand / WaitCommand / ZapCommand / ...
  step.py          step(world, cmd, rng) -> [Event]   <- the heart
  rules.py         dice, resistances, apply_damage, status tickers,
                   process_events (the event-apply choke point)
  worldgen.py      the 3-level demo dungeon (lazy level generation)
  traps.py  zap.py  potions.py  scrolls.py  spells.py  hunger.py
  worn.py  rings.py  pickup.py  stairs.py  occupation.py
  uhitm.py  mhitu.py  weapon.py  vision.py  energy.py  props.py
  objects*.py  monst*.py  mondata*.py  o_init.py  items.py
               the C tables (declarations / data / API split)
  isaac64.py  rnd.py  hacklib*.py
               the RNG core + the hacklib helpers
ui/              console rendering + key input (the only I/O)
main.py          ~40-line game loop gluing core to ui
tests/           pytest suite
```

## Run

```
python main.py
```

WASD / arrow keys to move, bump a monster to attack it, `g` to pick
up, then `w` / `t` / `r` / `z` / `c` / `e` + an inventory letter to
wear, take off, read a scroll, zap a wand, cast a book or eat a food
(letters are the inventory letters on the screen; beam actions ask
for a direction), `q` to quit.  `>` goes down the stairs, `<` climbs
back up: the dungeon has 3 levels, level 2+ generates on first visit
and stays intact when you come back, and reaching the bottom level
wins.  The status line shows the computed effective `AC` (base 10
minus the worn gear -- go get the floor armour), the spell `Pw` (a
level-N book costs 5*N Pw, slow regen) and the hunger gauge: it
drains 1/turn, fainting / starving / choking are live, and a big
food is a multi-turn meal a nearby monster interrupts (eating the
same item again resumes it).  The floor items wear their NetHack
glyphs (the defsym.h object-class table) -- `?` scrolls, `)` weapons,
`[` armour, `+` spell books, `/` wands, `>` / `<` the stairs.  The
floor kit: the demo scrolls (enchant weapon/armor, remove curse,
teleportation, blank paper), the wands (striking, cold) and the books
(magic missile, cone of cold, healing); the cursed floor cloak only
comes off after a remove curse scroll.

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
mypy              # run from the repo root
```

The config is in `pyproject.toml` under `[tool.mypy]`: it pins what a
bare `mypy` checks (`core`, `ui`, `tests`, `main.py`, `conftest.py`)
and disables the two error codes the C-style tables structurally
produce (`has-type`, `attr-defined`); everything else is reported,
and the strict flags are switched on one at a time as the error count
reaches zero.

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
can read the members from (the functional `IntEnum` API keeps the
members run-time-only, so `ObjType.DAGGER` would be an error at every
use site, and no annotation at the use sites can help).

