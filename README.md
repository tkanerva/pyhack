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
  spells.py        spell beams / fireball
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

WASD / arrow keys to move, bump a monster to attack it, `q` to quit.

## Test

```
pip install -r requirements-dev.txt
pytest            # run from the repo root
```

The tests are deterministic: the core takes an injected
`random.Random` (or any object with `randint`/`choice`), and `tests`
includes a `SeqRng` helper for exact roll-by-roll control.
