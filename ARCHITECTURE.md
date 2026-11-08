# PyHack architecture

## The rule

All game state lives in **one `World` object**. One function —
`step(world, command, rng) -> list[Event]` — advances the game by one
turn. The core has **no I/O, no global state, and no broadcast bus**:

```
 ui/console.py (keys, screen)           main.py (loop)
        | Command                              |
        v                                      v
   step(world, cmd, rng)  ---------------->  [Event, Event, ...]
        |
        +-- per-turn upkeep        (rules.tick_actor, energy.py,
        |                          rings.tick_rings, hunger.py)
        +-- movement / bump-attack (step.py; the C-port melee via
        |                          uhitm.py / mhitu.py)
        +-- traps                  (traps.py: TRAP_EFFECTS registry)
        +-- zaps                   (zap.py)
        +-- potions                (potions.py)
        +-- scrolls                (scrolls.py: the read.c subset)
        +-- spells                 (spells.py)
        +-- eat                    (hunger.py; a multi-turn meal is the
        |                          C occupation, ticked by occupation.py)
        +-- wear / take off        (worn.py: slots + the computed AC)
        +-- rings                  (rings.py: on/off + discovery)
        +-- pickup                 (pickup.py: the pickobj subset)
        +-- inventory              (invent.py: the pack + its letters,
        |                          the single writer of where an item
        |                          is; PLAN-INVENT.md)
        +-- stairs                 (stairs.py: the do.c / dungeon.c subset)
        +-- doors                  (doors.py: the lock.c doopen / doclose subset)
        +-- vision                 (vision.py: the vision.c port)
        +-- display                (display.py: what the hero remembers
        |                          of the map, the display.c port; the
        |                          glyph space is glyph.py)
        +-- monster genesis        (makemon.py: the makemon.c funnel;
        |                          place.py: goodpos / enexto)
        +-- object genesis         (mkobj.py: the mkobj.c funnel, the
        |                          containers, mkgold)
        +-- rules                  (rules.py: dice, resist, apply_damage,
                                        level_difficulty, process_events)
```

Events are frozen dataclasses. The UI renders `MessageEvent`s; tests
assert on the whole event list *and* the resulting world state.

## Why not the old broadcast/actor model

In single-threaded Python, a "message to an actor" is a function call
with extra indirection. The old code had **both** a message layer
(`MessageRouter`, `world.broadcast`, TypedDict messages) **and** direct
calls with direct attribute mutation (`entity.hp -= dmg` in
`TrapActor._apply_trap_effect`, `mon.attack(hero)` in `game.py`,
`react_to_damage` everywhere). That combination caused a concrete bug:
trap damage was applied **twice** (once in `TrapActor`, once in
`check_and_trigger_traps`). With one transition function and one
mutation choke point (`rules.apply_damage`), that bug class cannot
happen, and every state change is visible in a debugger.

Events-as-data keep the decoupling the broadcast was aiming for (UI,
sound, replay, tests all just consume the list) without the invisible
bus — and a recorded `(Command, [Event])` sequence *is* a replay.

## Old file -> new home

| old file      | new home                                   |
|---------------|--------------------------------------------|
| `contracts.py`| enums split into `core/types.py`; the TypedDict message schemas, `BaseActor`, `MessageRouter` and `Protocol`s are **deleted** (they were dead weight: nothing sent those messages, `world.query` always returned `None`) |
| `game.py`     | `core/step.py` + `core/worldgen.py` + `main.py` + `ui/console.py` |
| `player.py`, `monster.py` | `core/types.py` — one `Monster` dataclass; the hero is a monster with `is_hero=True` |
| `trap.py`     | `core/traps.py` — data + `TRAP_EFFECTS` registry, no actor |
| `zap.py`      | `core/zap.py` |
| `potion.py`   | `core/potions.py` |
| `spell.py`    | `core/spells.py` |
| `priest.py`, `pray.py` | the broken sketches were dropped, never ported; the C originals (`src/priest.c`, `src/pray.c`) are still unported (see "Suggested next steps") |
| `game.py`'s monster spawns | `core/makemon.py` (the `src/makemon.c` port) + `core/place.py` for `goodpos` / `enexto` (`src/teleport.c`); the object kit -> `core/mkobj.py` (`src/mkobj.c`) |

## Behaviour decisions

**Preserved from the old demo:** 30% trap-trigger roll; d20 vs
`20 - AC` hit formula; all damage dice (1d6 pit, 1d12 spiked pit,
1d6 fire, arrow 1d6 / dart 1d4 with `max(5, 20-AC)` hit chance,
boulder 4..20); monster stats (Goblin 8/AC7/dmg2, Orc 15/AC5/dmg4,
Bat 4/AC3/dmg1); hero 25 HP, effective AC 5 (base 10 in the starting
chain mail — the defence is now computed, see below); 40x20 level-1
map with 15 interior walls; 10 traps of the same four types; 9
monsters; `random` seed 42; the emoji log strings.

**Fixed (latent bugs in the old code):**
- Trap damage applied twice (see above) — regression test:
  `tests/test_traps.py::test_pit_deals_exactly_one_damage`.
- Teleport traps used a hard-coded 80x22 area while the map is 40x20 —
  teleports now always land on an in-bounds floor tile.
- A random wall / trap / monster could spawn on the hero's starting
  tile — `worldgen` keeps `(20,10)` free.
- Arrow keys never worked: the old code lower-cased the key and then
  compared against `"\x1b[A"`.
- Monsters could walk onto the hero or onto each other.
- Pressing enter ("wait") re-rolled the trap under the hero's feet;
  `WaitCommand` is now a true pass.
- The broken blessed/cursed potion inversion (flipped on every quaff)
  is dropped.

**Added (NetHack-faithful; the architectural choices — the session
details live in the PLAN-*.md files and the module docstrings):**

- Defence / armour (PLAN-ARMOR.md, Phases 1-4): the worn state is the
  C mechanism — `Item.owornmask` (the prop.h bitmask) + an inventory
  scan (`worn.which_armor` / `setworn`), no per-slot fields;
  `Monster.ac` is the BASE body AC and the effective AC is the
  computed `worn.uac()` (C `find_ac`), never cached; `mattacku`'s
  differential reads `AC_VALUE(uac)` (the roll only for negative AC).
  Phase 4 (erosion) is counters (`oeroded` / `oeroded2`) that
  `ARM_BONUS` / `uac` read on every query — no cache invalidation;
  the live call sites are the fire trap and the acid passive attack.
- Bump-to-attack: walking into a monster attacks it (the old demo had
  no hero attack at all, so the game was a death-watching exercise).
  Hero melee uses the same hit formula with 1d2 damage.
- A monster adjacent to the hero attacks instead of moving.
- Sleep / stuck / confusion / poison now tick down each turn
  (`rules.tick_actor`); poison deals 1 damage per turn
  (NetHack: 1d4 every 4 rounds — simplification).
- Wands discharge (consume a charge) even when they hit a wall; beams
  stop at the first monster (NetHack behaviour; the old spell.py beam
  hit everything in range).
- The demo plays the committed C-port combat in both directions: the
  demo monsters carry their PerMonst types (goblin / hill orc / bat;
  the monster->hero hits come from the mhitu attack tables) and the
  hero starts wielding a short sword (the uhitm subset on
  weapon.py's hitval / dmgval; backstab and the weapon special
  effects are deferred).
- Property system, the query half (core/props.py): C's `u.uprops[]`
  split two ways — the intrinsic state is a set on the monster; the
  extrinsic contribution of the worn gear is derived on every query
  from the `owornmask` scan (the computed-never-cached style).  The
  per-type `<Type>_on()` / `<Type>_off()` side effects and the
  UP_BLOCKED / UP_TEMP / UP_ARTIFACT halves stay STUBs (the props.py
  docstring).
- Scroll reading (core/scrolls.py, the read.c port): `ReadCommand`
  (C: 'R'/'r') + `read_scroll()` implement the first five C
  `seffects()` — blank paper, enchant weapon, enchant armor, remove
  curse, teleportation; the remaining seventeen handlers are STUBs
  (each with its C provenance in the module docstring).  The
  teleport collapses C's cursed level-teleport and the blessed
  getpos destination to the random floor-tile set.
- Rings (PLAN-RING.md, core/rings.py): donning / doffing a ring is a
  *producer* — `ring_on` / `ring_off` emit the `DiscoveryEvent` + the
  attribute messages, and the identity mutation (`Item.dknown` /
  `Item.known`, the per-game `oc_name_known` / `oc_encountered`) is
  applied only in the core choke point `rules.apply_discovery` via
  `process_events` (the DamageEvent / StatusEvent pattern).  The
  ability an ability-ring changes is computed, never cached
  (`rules.current_ability`, the `uac` style), so it feeds to-hit for
  free; the per-turn effects are `rings.tick_rings`; the remaining
  ring effects are STUBs (the rings.py docstring).
- The stairs system (PLAN-STAIRS.md, core/stairs.py): stairs are
  TERRAIN (`TerrainType.STAIRS` + `Tile.stair_dir`, C: the `ladder`
  mask) plus per-level STAIRWAY RECORDS (`World.stairs`), not traps.
  `World.map` is the CURRENT level; visited levels are parked in
  `World.levels` (memory is the save file — coming back up restores
  everything).  Entity level-membership (`Monster.lev` / `Trap.lev` /
  `Item.lev`) is filtered in exactly four places (`World.monster_at`,
  `World.items_at`, `check_traps`, `step`'s monster loop) — a missed
  filter is a cross-level ghost.  Levels 2..N generate lazily in the
  C mklev draw order; the transition mirrors C `goto_level`'s order;
  reaching `World.max_lev` wins.  The deferred list is
  PLAN-STAIRS.md §5.
- The display layer (core/display.py + core/glyph.py, the src/display.c
  port): the screen is the hero's MEMORY of the level, not the true
  terrain.  `Tile.glyph` (C: `levl[x][y].glyph`) starts at
  `GLYPH_UNEXPLORED` and is written only by `newsym()`, and only where
  `can_see()` is true; `Tile.seenv` (the C seen vector) records the
  octants a square was seen from, so a wall the hero has not seen draws
  as stone.  `render()` calls `display.docrt()` first -- C's window
  port does the same before a redraw -- and then paints `Tile.glyph`,
  overlaying monsters and trap effects live (they are never remembered).
  Objects and known traps *are* remembered, so they survive out of
  sight; the level change needs nothing special, because the memory is
  tile state and is parked with the Map in `World.levels`.  `glyph.py`
  is C's glyph space + defsym.h symbol table (S_* -> character), which
  is also what replaced the renderer's hand-rolled glyph switches: walls
  are now `|` / `-`, corridors `#`, doors `+` closed and `|`/`-` open.
  Blindness withholds every IN_SIGHT bit (vision.c's `else if (Blind)`),
  so a blind hero sees only his memory.  STUBs: lighting (an unlit floor
  draws as stone), `wall_angle()`'s wall_info modes, the per-species
  monster glyphs.
- The hunger system (PLAN-HUNGER.md, core/hunger.py): the C 5.0
  0..2000 gauge + seven-state machine as data on `Monster`
  (`uhunger` / `uhs` / `fainted`); the per-turn ticker runs in the
  hero phase of `step` while the hero is fainted too (that is how a
  faint deepens into starvation); a big food is the C occupation
  (core/occupation.py) — the meal consumes the following turns, a
  nearby monster interrupts it, and eating the same item again
  resumes it.
- The experience system (PLAN-EXPERIENCE.md, core/experience.py): the
  exper.c port as pure functions over World.  The 5.0 structure:
  `struct permonst` has no `mexp` column, so the kill XP is COMPUTED
  from the monster's instance level (`m_lev`, pinned to
  `mdata.mlevel` at spawn — the zero-draw house rule), effective AC,
  speed and attack table.  The grant sits in the death choke point
  (`rules.apply_damage`, hero-caused kills only — C: the mon.c kill
  wrapper; 5.0's mondead does not grant XP); the zap damage sources
  are normalized to the caster id so wand / spell kills flow through
  the same gate.  Level-ups give the draw-free `newhp` (base 2 + the
  C CON table) + the `energy.newpw` Pw (its ONE draw is the only draw
  of the whole XP path, at the first level-up), under the AD&D
  at-most-one-level rule; `losexp` (the drain path) is ready for the
  mhitu AD_DRLI port.  `ueninc[]` is the per-level Pw INCREMENT (C
  newpw records it, losexp subtracts it) — not the regen period, which
  tick_energy computes from the level (C `regen_pw`).  The deferred
  list is PLAN-EXPERIENCE.md §5.
- The inventory core (PLAN-INVENT.md phase A, core/invent.py): the
  port of the item half of src/invent.c, and the **single writer** of
  the PACK half of an item's where-state (`addinv` / `freeinv` /
  `useup` / `useupall` / `delobj`); the floor half stays in
  core.mkobj (`place_object` / `add_to_container` /
  `delete_contents`), exactly C's invent.c / mkobj.c split.  The old
  fourth writer `items.consume_item` is deleted (its call sites are
  `invent.useup`), `worn._remove_destroyed` is `invent.delobj`,
  `pickup` and the starting kit go through `addinv`, and the
  `conftest.assert_item_locations` invariant (exactly one place per
  item, every id resolves) is the tripwire for a new one.  Letters are
  **assigned once** (C: `assigninvlet` walking a..z A..Z from
  `World.lastinvnr`, the C `gl.lastinvnr`), so `Item.invlet` -- not an
  index into the pack -- is what `ui/console._item_by_letter` looks
  up: dropping or picking up an item no longer re-letters the rest of
  the pack (the letter-drift defect).  `Item.charges` is retired in
  favour of C's `spe` (the wand / book / tool charge field), and
  `useup` is the one "one of these is gone" path, so eating the last
  of a stack or destroying a chest cannot orphan the contents.  The
  **display half** (phase F, the non-menu path) is a set of pure
  formatters in the same module -- `xprname`, `display_inventory` (the
  `i` list and its per-class subsets, class headings from
  `let_to_name`), `is_inuse` / `display_in_use` (`*`), `money_cnt` /
  `doprgold` (`$`) -- over a reduced `doname` that reads the stored
  `Item.name`, the stack count and the `(being worn)` / `(wielded)`
  tail.  The console turns those keys into a `ListCommand`, answers it
  itself (`ui.console.inventory_lines`) and `core.step` returns nothing
  for it: **a listing is a render, not a turn** (C: ECMD_OK).  Still
  open from the plan: merging (`mergable` / `merged`, phase B), the
  naming slice (`core/objnam.py`, phase C -- it replaces `doname`),
  weight / encumbrance (phase D), gold (phase E), the menu half of the
  display and `prinv` (phase F), `getobj` / selection (phase G) and
  `#adjust` (phase H).
- The level generators (WAVE3.md / PLAN-MKLEV.md, core/mklev.py,
  core/mkroom.py, core/mkmap.py, core/doors.py): `new_world(rng,
  generator="demo"|"mklev"|"cavern")` behind a switch that defaults to
  the pinned cave (no rng draw gained or lost on the demo path);
  "mklev" is the ported rooms + corridors + doors generator (C
  mklev.c / mkroom.c / sp_lev.c / rect.c), "cavern" the cellular
  automaton (C mkmap.c).  Rooms are level state -- `Map.rooms` /
  `subrooms` / `doors` / `flags`, the identity-compared `Room`,
  `Tile.roomno` / `edge` / `lit` / `horizontal` with the C NO_ROOM /
  SHARED / ROOMOFFSET -- parked with the map in `World.levels`.  No
  ambient level globals: the Map is a parameter, the transient arrays
  are arguments (what lets a lazy level be generated while the hero
  stands on the previous one -- the niche carve used to take
  world.map and hit the parked level; map_ is threaded through).  Doors
  are terrain + a system (`core/doors.py`, C lock.c): walking into a
  closed door opens it (C domove), `x<direction>` closes one
  (CloseCommand).  Draw order is preserved through the STUBs; the
  documented divergences are PLAN-MKLEV.md §3.  The generated paths
  draw through C's RNG (`rn2` / `rnd` / `rn1` / `rnl` / `d` / `rne`),
  which `random.Random` does not have, so the caller picks the stream:
  `main.make_rng()` keeps `random.Random(42)` for the pinned cave and
  hands `core.rnd.Rng` to `--mklev` / `--cavern`, and
  `worldgen.require_c_rng()` refuses the wrong one at the entrance to
  the generators instead of letting it fail in the middle of
  `makelevel`.

**Intentional simplifications (documented, not bugs):**
- The monster and object genesis (WAVE 4a/4b, core/makemon.py,
  core/mkobj.py, core/place.py): `makemon()` is C's funnel -- position,
  then type (`rndmonst_adj`'s weighted reservoir sample), then hit
  points (`adj_lev` / `newmonhp`), then gender, then mood
  (`peace_minded` / `set_malign`), then inventory -- and it returns
  `Optional[Monster]`, because C's NULL is a normal answer (no legal
  square, a genocided species, an extinct population).  The level being
  stocked is a parameter (`map_`, `lev`, `in_mklev`), so a lazy level is
  built while the hero stands on another one; `World.monster_at_lev` is
  the single occupancy filter, and `World.hero_or_none` /
  `World.hero_ulevel` are the two hero reads that work before there is a
  hero at all (level 1 is generated first; C reads `u.ulevel` = 1 and an
  unplaced `u_at()` and gets the same answers).  `goodpos()` is C's,
  including its early returns on water and lava and the closed-door half
  of `accessible()`.  `mkclass` / `MongenOrder` walk the
  per-class generation order, `MonState.propagate` counts births and
  makes a species extinct, and `mkobj` is the object half: a subset per
  class, with `Item.contents` (a list of ids) as the only containment
  and `weight()` ported whole -- an object is registered in
  `World.items` when `mksobj()` builds it, and `place_object()` /
  `add_to_container()` then set its where-state.  Still STUBs inside
  them, each named in the module docstrings: `m_initweap` /
  `m_initinv` (the 400-line species weapon tables), monster groups,
  mimics, shapechangers, the timers (corpse rot / eggs / oil / ice),
  artifacts, `splitobj`, and container merging.  The monster table is
  C's, whole: `tools/convert_monsters.py` parses
  `include/monsters.h` and rewrites `core/monst_data.py` in C order
  (383 rows, one per `MON(...)`, so nothing renumbers), which is what
  makes `rndmonst_adj` / `mkclass` the real distribution.  There is no
  alignment system yet, so
  `peace_minded()` runs on the constant `World.hero_align` = A_NEUTRAL.
- Monster AI: a monster that can see the hero (the ported vision,
  core/vision.py) chases with a greedy single step; the full
  `mmove()` (doors, fleeing, remembered positions, M2_WANDER, waking
  sleepers by sound) is future work.  A monster that cannot see the
  hero random-walks (C: wander).
- Web/pit "stuck" lasts 10 turns (NetHack: escape checks).
- Spell study/learning mechanics dropped; books have pages (`spe`)
  only.
- Spell damage is a flat 2d6 (the old `d6 * nd` referenced a stat that
  never existed).
- `src/priest.c` / `src/pray.c` are unported (the old Python sketches
  were dropped, never ported); they land as core systems — functions
  over `World` returning events — from the C originals (see
  "Suggested next steps").

## Testing

- **Rules** are pure functions: table-driven unit tests, no mocks
  (`tests/test_rules.py`).
- **step()** is a function: build a tiny world with `conftest.make_world`,
  feed a command, assert on world state *and* the event list.
  `SeqRng` (in `conftest.py`) presets exact dice rolls.
- **Whole games** are deterministic: `new_world(random.Random(42))` +
  a command list reproduces byte-for-byte
  (`tests/test_step.py::test_same_seed_same_game`).  The rng is the
  caller's: a `random.Random` (or any object with
  `randint`/`choice`/`shuffle`) drives the demo cave, `core.rnd.Rng`
  drives a generated level -- `main.py`'s `make_rng(generator)` is the
  one place that decision is made, and
  `test_the_demo_entry_point_builds_and_steps_every_generator` runs it
  for all three generators.  `tests/test_main.py` runs `main()`
  itself, with the keyboard scripted and only the console faked: the
  shell's loop had no test until the `--mklev` rng fix.

## Suggested next steps

Wave 4a/4b has landed (core/makemon.py / core/mkobj.py /
core/place.py; the 480-row `mksobj` smoke; generated levels stocked
from the tables; the demo still byte-identical), and so has the monster
table: `tools/convert_monsters.py` reads `include/monsters.h` and
rewrites `core/monst_data.py` in C order, so `mons[]` is the whole 383
rows and `rndmonst_adj` / `mkclass` draw the real distribution (every
corpse, statue and special room reads it; a half-filled table makes
bugs look like tuning, PLAN-MAKEMON §4.6).  The queue, in dependency
order (item 1 LANDED: `set_levltyp` + `mkfount` / `mksink` /
`mkaltar` / `mkgrave` in core.mklev, `fill_ordinary_room`'s
fountain / sink / altar / grave rolls taken in C order, `Tile
.altarmask` + the AM_* / `align2amask` block in core.monst_defs —
the same writer Wave 5's `mkswamp` and the temple altar need):

1. **Wave 5: special rooms** (PLAN-SPECIAL-ROOMS.md), in the plan's
   own staging: the temple first (needs `src/priest.c` / `src/pray.c`
   as core systems and the `Monster.epri` extra — makemon already
   accepts-and-ignores MM_EPRI / MM_ESHK), then the zoo family
   (`fill_zoo` / `courtmon` / `squadmon` / `morguemon` / `antholemon`
   / `mkundead` / `mk_zoo_thronemon` become `mkclass` + `makemon`
   fill-ins), the shops last (shk.c is billing before it is a room).
2. **The genesis residue** (independent of 1, interleavable):
   phase E's `m_initweap` / `m_initinv` species tables (monster
   inventories; the `mongets` / `mkmonmoney` mechanism is in),
   phase F's groups / `grow_up` / `clone_mon` / `create_critters`,
   `splitobj` + the container / pickup merge rules, the rust / rot /
   corrode half of `mkobj_erosions`, and the fire-trap-erodes-armour
   regression test.  (The `Item.charges` -> `spe` migration is DONE —
   it landed with PLAN-INVENT.md phase A.)
3. **Wave 6: the inventory core** (PLAN-INVENT.md / PLAN-PICKUP.md /
   PLAN-DROP.md — invent.c / pickup.c / do.c + wield.c): phase A is
   in (`core/invent.py`: the pack, the letters, the single writer) and
   so is phase F's display half (`display_inventory` / `xprname` /
   the reduced `doname`; the console's `i` family, which costs no turn);
   the rest of the plan's staging — stacking (B), naming (C), weight /
   encumbrance (D), gold (E), selection (G) —
   is what turns the pack into NetHack's, and it consumes 2's merge
   rules and `splitobj`.
4. **The small UI debt**: wire `QuaffCommand` (zap / cast / eat are
   wired; `q` quits, so the quaff key is to choose).
5. **Scrolls**: fill in the STUBs of `core/scrolls.py` as their
   machinery lands (the C provenance of each is in the module
   docstring); next candidates on existing machinery:
   SCR_DESTROY_ARMOR (the wrapper around the already-real
   `worn.disintegrate_arm`), SCR_LIGHT (a `lit` flag on Tile),
   SCR_CONFUSE_MONSTER (rules over nearby monsters).
6. **Full monster AI** (`mmove()`) on the ported vision: doors,
   fleeing, remembered positions, M2_WANDER (the greedy single-step
   chase is in).
7. **Wave 7 / 8, then the special levels**: throwing (PLAN-THROW.md,
   dothrow.c + mthrowu.c), breath weapons (PLAN-BREATH.md, the
   zap.c dobuzz beam engine), then PLAN-SPLEV.md's `des` API + the
   lua level programs (the most parallelisable piece left).
8. If the system/entity matrix grows, evolve into a lightweight ECS
    — the events-out design stays the same.

Also due: rerun `nethack_index/tools/generate_index.py` — INDEX.md
was generated before Wave 4a/4b landed and still lists makemon.c /
mkobj.c as unported; and PLAN-EXPERIENCE.md / PLAN-ARMOR.md's status
headers predate their own landings (both systems are in and tested),
so the next session touching either should refresh the header in the
same commit.  The one manual step the table leaves is running the
converter: the generated rows are checked in, and `--check`
tells you whether the file on disk still matches the C header.
