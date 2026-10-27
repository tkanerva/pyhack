# Plan: hunger system (the eat.c port)

**Status (this round):** the basic subset is implemented and tested —
the `uhunger`/`uhs` data on the hero, the per-turn ticker (C
`gethungry()`), the `newuhs()` state machine (satiated → not hungry →
hungry → weak → fainting → fainted → starved), fainting (the
`fainted` counter + the `unfaint()` recovery line), starvation and
choking deaths, eating (the `doeat()` food subset: find, the edibility
refusals, the taste feedback, the nutrition via `lesshungry()`), the
spell-casting gate (C `spelleffects_check`'s "too hungry" line), the
botl status text, the demo floor food and the `e<letter>` key.  The
deferred items are section 5, each with its C provenance and the
machinery it lands with.

Ground truth is the NetHack 5.0 C source (local clone at `../NetHack`).
NetHack 5.0 **reworked** the hunger system relative to 3.6: the gauge
is a 0..2000 `uhunger` (start 900, negative = starving) with a seven-
state `uhs` machine (the `hunger_state_types` enum, include/hack.h)
instead of the old `HUNGRY`/`FULL`/`PECKISH` band macros, and the
per-turn decrement carries a randomized `rn2(20)` "accessory time"
(eat.c `gethungry()`) instead of the old `moves % N` schedule.  This
port follows 5.0, the committed version.

## 1. What the C code actually does (reference)

| Mechanic | C location | Notes |
|---|---|---|
| Gauge + state | `include/you.h` `u.uhunger` (int), `u.uhs` (unsigned); `include/hack.h` `enum hunger_state_types` (SATIATED=0 … STARVED=6); `src/eat.c` `init_uhunger()` (start 900 / NOT_HUNGRY) | called from `u_init.c`, `end.c` (life-saving / post-game) and `pray.c` |
| Per-turn ticker | `src/allmain.c` main loop → `src/eat.c` `gethungry()`: the main `uhunger--` (carnivorous / herbivorous / metallivorous, `!Slow_digestion`, `(!Unaware \|\| !rn2(10))` — `Unaware` is *fainted/unconscious*, i.e. metabolism slows 9/10 while fainted), then `accessorytime = rn2(20)` (5.0: randomized, anti ring-juggling) with the odd/even branches: odd → `--` on regeneration (non-form), `--` on encumbrance `> SLT_ENCUMBER`; even → `--` on the Hunger property, `--` on Conflict, and the even cases 0/4/8/12/16 → armor slow-digestion / left ring / worn amulet / right ring / carried real Amulet; then `newuhs(TRUE)` | the ring cases: a worn ring burns if `spe != 0` or its type is not `oc_charged`, except MEAT_RING (plus a +0-ring-of-protection special case that reads the extrinsic `EProtection` — see simplifications) |
| State machine | `src/eat.c` `newuhs(incr)`: thresholds `>1000 SATIATED, >150 NOT_HUNGRY, >50 HUNGRY, >0 WEAK, else FAINTING`; FAINTING: `uhunger_div_by_10 = sgn(h) * ((abs(h)+5)/10)` (negative for h < 0 — the deeper the deficit, the WIDER the faint roll and the LONGER the faint), fainted → FAINTED, `uhs <= WEAK \|\| rn2(20 - div) >= 19` → faint (duration `10 - div`, Deaf, nomul, "You faint from lack of food."), else `h < -(100 + 10*CON)` → STARVED ("You die from starvation."); on a state change: `ATEMP(A_STR)` = −1 entering WEAK / 0 leaving it, the HUNGRY ("You feel hungry." / "You are beginning to feel hungry." / "You only feel hungry now.") and WEAK ("You feel weak." / "You are beginning to feel weak." / "You are still weak.") messages (the `<145` / `<45` splits), and the `hp < 1` → "You die from hunger and exhaustion." guard | the `hu_stat[]` bottom-line texts ("Satiated", "", "Hungry", "Weak", "Fainting", "Fainted", "Starved") are also in eat.c; the botl prints them when `uhs != NOT_HUNGRY` (src/botl.c) |
| Faint recovery | `src/eat.c` `unfaint()` (the nomul's afternmv): `Hear_again()` (50% deaf cured), `if (uhs > FAINTING) uhs = FAINTING;` | the C nomovemsg when the faint ends is "You regain consciousness." |
| Eating | `src/eat.c` `doeat()`: `floorfood("eat")` (floor prompt + `getobj` selection), the `is_edible()` refusals ("You cannot eat that!"), the worn-food refusal, the multi-turn occupation (`reqtime` = `oc_delay` scaled by remaining `oeaten`, bites via `bite()`, interruption via `reset_eat`); `fprefx()` first-bite messages (the FOOD_RATION / TRIPE_RATION / … cases + the give_feedback default "This X is delicious!"/"terrible!"); `lesshungry(obj_nutrition)` | the demo subset is one turn (house rule: a quaff / a read / a cast all cost one turn), full nutrition at once |
| Nutrition | `src/eat.c` `lesshungry(num)`: `uhunger += num`; `>= 2000` → `choke()` (only when the pre-meal state was SATIATED — C `canchoke`); `>= 1500` → "You're having a hard time getting all of it down." (the `fullwarn`, once per meal); `newuhs(FALSE)`; `morehungry(num)`: `uhunger -= num; newuhs(TRUE)`; `choke()`: the `!rn2(20)` survive roll → "You stuff yourself and then vomit voluminously." + `morehungry(Hunger ? (uhunger-60) : 1000)` + `vomit()` (nomul −2), else "You choke over your food." + death (killer "Choked on …") | `obj_nutrition()` = `objects[otyp].oc_nutrition` for ordinary food (corpse → `cnutrit`; the demo carries no edible corpse) |
| Other call sites | `potion.c` `peffect_water` (`uhunger += rnd(10)`), `peffect_whiskey` (`10 * (2 + bcsign)`), `fountain.c` (`rnd(10)`); `spell.c` `spelleffects_check` (`uhunger <= 10` → "You are too hungry to cast that spell.", no time); `uhitm.c` (purple-worm swallow, `u.uhunger += (cnutrit+1)/2`); `polyself.c` (`uhunger = rn1(500,500)`); `end.c` (post-death `init_uhunger` for < 500) | none of the demo's potion types (healing / confusion / polymorph / sleeping sickness / cancellation / increase AC) is a water / whiskey — no potion nutrition this round |

Already in pyhack that the port builds on:

- `core/types.py` `Monster` — the status counters (`sleeping`, `stuck`,
  …) that the new `fainted` counter joins; `ucon` (the starvation
  threshold reads it, as C reads `ACURR(A_CON)`).
- `core/objects.py` — the full food rows with `oc_nutrition` and
  `oc_delay` (the FOOD table in `objects_data.py`), `ObjClass.FOOD`,
  `Prop` (HUNGER / CONFLICT / SLOW_DIGESTION / REGENERATION),
  `W_RINGL` / `W_RINGR` / `W_AMUL`.
- `core/worn.py` `which_armor` — the ring / amulet queries of the
  `gethungry` accessory cases.
- `core/rules.py` `tick_actor` (the per-turn status upkeep — the home
  of the faint tick), `apply_damage` (the death choke point),
  `sgn` (via `core.hacklib`).
- `core/items.py` `consume_item` — the meal's `useup`.
- `core/spells.py` `cast_spell` — the check pipeline the "too hungry"
  gate joins.
- `core/hunger.py` does not exist yet — it is the new module.

## 2. Design decisions (decide once, keep consistent)

1. **One command, one entry point.** `EatCommand(item_id)` (C: 'e' —
   `doeat`) → `step()` → `hunger.eat_food()`, exactly the
   `QuaffCommand` / `ReadCommand` pattern.  Pure function over
   `World`, events out, injected `rng`.
2. **Data on `Monster`:** `uhunger: int = 900`, `uhs: int = NOT_HUNGRY`
   (the C start, `init_uhunger`), `fainted: int = 0` (C: the FAINTED
   state plus the `nomul(-duration)` unconsciousness — the Deaf half is
   dropped, pyhack has no deafness).  A `HungerState` IntEnum in
   `core/types.py` with the C values 0..6.
3. **The ticker runs in the hero phase of `step()`, after the ring
   tick, before the alive check** — C calls `gethungry()` from the main
   loop once per round, and it runs while the hero is fainted / asleep
   too (that is how a faint deepens into starvation).  `tick_actor`
   ticks `fainted` down (it is a status like the others); reaching 0
   emits the C nomovemsg "You regain consciousness." and performs
   `unfaint()`'s `uhs > FAINTING → FAINTING` fixup.  A fainted hero
   gets no action, gated the same way an asleep one is (`is_asleep
   || is_fainted` on the `was_asleep` gate).
4. **Draw-order discipline (the one deviation from C, documented):**
   C 5.0 draws `accessorytime = rn2(20)` **unconditionally** per round;
   pyhack draws it **only when at least one accessory branch can burn**
   (a worn ring / amulet, a carried real Amulet, or the
   regeneration / Hunger / Conflict / slow-digestion properties).  The
   bare demo hero therefore costs **zero draws per turn** — the exact
   zero-draw house rule that kept `AC_VALUE` and the scroll port from
   touching the seeded suite — and the moment the hero wears the +1
   ring of protection the C draw order resumes.  Same for the faint
   metabolism roll (C `!rn2(10)`, only while fainted) and the
   `newuhs` faint roll (only in the FAINTING branch).
5. **One-turn meals.** C's multi-turn occupation (`reqtime`, bites,
   `reset_eat`, the "resume your meal" path, `oeaten` bookkeeping) is
   dropped — the house rule is one turn per use (quaff / read / cast).
   Full nutrition at once via `lesshungry(obj_nutrition)`; the whole
   item is consumed (the demo food is quantity 1; no splitting).

   **SUPERSEDED (PLAN-OCCUPATION.md):** the multi-turn meal is now the
   C occupation, as a generator (`core.occupation` + `core.hunger.
   _meal`).  Decision 5 stands for the OTHER one-turn uses (quaff /
   read / cast) only; the delay-1 foods (apple / orange / melon)
   keep their one-turn behaviour.
6. **Death through the choke point.** Starvation and choking deaths go
   through `rules.apply_damage` (the only way an actor loses HP) with a
   new `DamageType.STARVING` (C: `done(STARVING)`, killer
   "starvation"; the choking killer "Choked on …" shares the type,
   the `DeathEvent.by` keeps "starvation" / "choking" distinct) and
   `message=False` (the module emits the specific C lines).
7. **The "too hungry" cast gate** (C `spelleffects_check`) joins
   `cast_spell` after the Pw check, before the failure roll: no time,
   no draw, no page.  C's `SPE_DETECT_FOOD` exception is irrelevant
   (the demo books have no such spell).
8. **Botl text.** The status line prints `HU_STAT[uhs]` (the C
   `hu_stat[]` table, "Satiated" / "Hungry" / "Weak" / "Fainting" /
   "Fainted" / "Starved"; NOT_HUNGRY prints nothing) — C botl.c.
9. **Demo food:** four floor items at FIXED positions reserved via
   `generate_map(keep_floor=...)` (apple, orange, food ration, melon —
   zero rng draws, the seed-42 layout / trap / monster placement and
   the `test_new_world_makes_no_new_rng_draws` sequence untouched).
   The hero starts at `uhunger = 900` (the dataclass default; C
   `u_init.c` `init_uhunger`).  No starting food in the kit (C new
   heroes carry none).

## 3. What lands this round (implemented)

| Area | Port | C provenance |
|---|---|---|
| `core/types.py` | `HungerState` IntEnum (C values); `Monster.uhunger` / `Monster.uhs` / `Monster.fainted`; `DamageType.STARVING` | you.h, hack.h |
| `core/hunger.py` (new) | `hunger_state()` (the `newuhs` threshold step); `newuhs()` (faint roll, starvation, the state-change messages, the exhaustion guard); `tick_hunger()` (`gethungry`: the main decrement incl. the fainted `!rn2(10)` slowdown, the accessory cases 0/4/8/12/16); `lesshungry()` (fullwarn, choke); `morehungry()`; `choke()` (the `!rn2(20)` survive / die); `eat_food()` (`doeat` subset: find, "You cannot eat that!", the worn refusal, `fprefx` subset, consume, `lesshungry`); `HU_STAT` (the botl texts) | eat.c, botl.c |
| `core/commands.py` | `EatCommand(item_id)` (+ the `Command` union) | 'e' |
| `core/hacklib.py` | `is_fainted()` (the status-query home) | the macro idiom |
| `core/rules.py` | `tick_actor` ticks `fainted` down; at 0 the C nomovemsg + the `unfaint()` `uhs` fixup | eat.c `unfaint` |
| `core/spells.py` | the `uhunger <= 10` cast refusal | spell.c `spelleffects_check` |
| `core/step.py` | `EatCommand` in the player turn; `tick_hunger` after the ring tick (runs while fainted / asleep, guarded by alive); the action gate `is_asleep \|\| is_fainted` | allmain.c |
| `core/worldgen.py` | `FLOOR_FOODS` (fixed positions, no rng draws) | — |
| `ui/console.py` | `e<letter>` key; the hunger text on the status line | botl.c |
| `tests/test_hunger.py` (new) | table-driven over the C branches with `SeqRng` (thresholds, ticker + draw audit, ring / amulet accessory cases, the HUNGRY / WEAK message matrix, the faint roll (both the `uhs <= WEAK` first-faint and the roll path), starvation, eating (refusals, feedback, nutrition), the fullwarn, choke survive / die, the step wiring, the cast gate) | — |
| `tests/test_worldgen.py` | the floor-food placement test | — |

## 4. Documented simplifications (not bugs)

- **The `ATEMP(A_STR)` weak penalty is dropped.**  C's `newuhs` sets a
  *temporary* strength of −1 while the state is WEAK and clears it on
  recovery; pyhack's abilities are `base + worn-ring spe`
  (`core.rules.current_ability`) with no base/temp split.  The WEAK
  state itself is tracked and messaged; the STR effect comes with the
  ability base/temp split (section 5.1).
- **No `EProtection` extrinsics in the ring cases.**  The C 5.0
  +0-ring-of-protection special case ("only source of protection"
  test) reads the worn-properties computation
  (`EProtection & ~W_RINGL`), which is the STUB'd intrinsic/extrinsic
  system (PLAN-ARMOR.md decision 7); the ported test is `spe != 0 or
  not charged` (the C `oc_charged` half of the same condition).
- **No encumbrance** (C's odd-branch `near_capacity() > SLT_ENCUMBER`
  decrement; pyhack has no capacity system — the `oc_big` / weight
  data stays in the table).
- **No multi-turn eating** (decision 5) — and with it: no interruption,
  no "resume", no `oeaten` weight bookkeeping, no the-tin case
  (`consume_tin` / `start_tin`), no floor-food prompt (the command
  names the item, like `ReadCommand`), no `touchfood` splitting.
- **No polymorphic edibility** (C `is_edible`'s fire-elemental /
  metallivorous / ghoul / gelatinous-cube branches): the demo hero is
  a fixed human — edibility is the `FOOD_CLASS` test, plus the two C
  refusals (non-food, worn).
- **No corpse / egg specifics** (rotted `cprefx`/`cpostfx`, poisoning,
  stoning, the egg's `corpsenm`, tins): the demo floor carries plain
  fruit / rations; the `fprefx` subset is the FOOD_RATION and
  TRIPE_RATION cases + the give_feedback default.
- **`vomit()` is the message only** (C's nomul −2 "you can move
  again", the yellow-dragon acid breath and the altar-wrath check are
  dropped — no multi-turn, no such monsters / altars).
- **No Deaf** (the faint's `HDeaf` half; the `Hear_again` 50% cure
  comes with a deafness port).
- **No `debug_hunger` option** (C `iflags.debug_hunger` — pyhack has
  no option system).
- **No conduct / livelog** (`uconduct.food`, vegetarian / vegan
  checks, `exercise(A_CON, FALSE)` in choke).
- **Potion / fountain nutrition is out** (none of the demo's potion
  types is water / whiskey; no fountain in the demo).

## 5. Deferred (later round, with their machinery)

1. **Ability base/temp split (`ATEMP`)** — `newuhs`'s weak −1 STR:
   split `Monster.ustr/ucon/ucha` into base + temp (C
   `uchain[].base/.temp`), `current_ability` reads base + temp + ring,
   and the WEAK transition sets / clears `temp[str]`.  Lands with the
   priest / align port (`adjalign`/`adjattrib` share the same
   machinery) — until then the WEAK state is tracked without its STR
   penalty.
2. **The intrinsic/extrinsic property system** (PLAN-ARMOR.md decision
   7) — unlocks the `HRegeneration` / `Hunger` / `HConflict` property
   reads of `gethungry` from *worn gear* (currently the ticker reads
   `mon.intrinsics` only — the demo hero has none, so this is
   behaviourally identical) and the `EProtection`-based +0-ring case.
3. **Encumbrance (`near_capacity` / `check_capacity`)** — the odd-
   branch decrement, the "Your concentration falters while carrying
   so much stuff." cast refusal (spell.c, next to the hunger gate),
   and the encumber_msg() of `init_uhunger`.
4. **Multi-turn eating (the occupation system)** — `reqtime` /
   `usedtime` / `nmod`, `bite()`, `reset_eat` / `do_reset_eat`,
   "You resume your meal.", the `oeaten` weight bookkeeping
   (`consume_oeaten`, `recalc_wt`, `eaten_stat`), the
   `paranoid_query` "Continue eating?" at the choke threshold.
   Lands with the general occupation / multi-turn port (the same
   machinery C's digging, opening and tins share).
5. **Tins (`start_tin` / `consume_tin` / `opentin`)** — the tin-opener
   tool, the `tintxts` variety table, rotten / homemade handling, the
   greasy-tin glib effect.
6. **Corpses and eggs as food** — `eatcorpse` (rotting age, poisoning,
   stoning, the `cprefx`/`cpostfx` intrinsics — giants give STR, the
   `corpse_intrinsic` pick), the egg's `corpsenm` (cockatrice,
   pyrolisk), `rottenfood`, the `nonrotting_corpse` exceptions.
   Lands with the corpse system (monster death drops).
7. **Polyself nutrition** (`polyself.c` `uhunger = rn1(500,500)`) and
   the polymorphic `is_edible` branches — land with the polymorph port.
8. **Potion / fountain nutrition** (`peffect_water` `rnd(10)`,
   `peffect_whiskey` `10 * (2 + bcsign)`, `fountain.c`) — land with
   the water / whiskey potion rows and the fountain tile.
9. **The purple-worm swallow** (`uhitm.c` `u.uhunger += (cnutrit+1)/2`,
   the `uhunger >= 1500` can't-digest check) — land with the swallow
   attack port.
10. **Deafness** (the faint's `HDeaf` / `Hear_again`) — land with a
    general deafness status.
11. **Conduct / livelog / discovery** (`uconduct.food`, the
    vegetarian / vegan conduct, `exercise`) — land with the conduct
    system.
12. **`end.c` bookkeeping** (post-death `init_uhunger` when
    `uhunger < 500`, the `CHOKING` high-score killer name) — land with
    the game-end / high-score port.

## 6. Files touched

| File | Change |
|---|---|
| `core/types.py` | `HungerState` enum; `Monster.uhunger` / `uhs` / `fainted`; `DamageType.STARVING` |
| `core/hunger.py` | **new** — the eat.c port (ticker, state machine, eating, choke) |
| `core/commands.py` | `EatCommand` |
| `core/hacklib.py` | `is_fainted` |
| `core/rules.py` | `tick_actor`: the fainted tick + recovery |
| `core/spells.py` | the "too hungry" cast gate |
| `core/step.py` | `EatCommand` + `tick_hunger` + the fainted action gate |
| `core/worldgen.py` | `FLOOR_FOODS` (fixed positions, no rng draws) |
| `ui/console.py` | `e<letter>`; the status-line hunger text |
| `main.py` | the banner |
| `tests/test_hunger.py` | **new** |
| `tests/test_worldgen.py` | the floor-food placement test |
| `README.md`, `ARCHITECTURE.md`, `CHANGES.md` | layout, behaviour decisions, keys |

Commit granularity: one commit per task (house style), in the order
types/commands → hunger module → step wiring → worldgen/ui → tests →
docs.

## 7. Risks / open questions

1. **The per-turn draw and the seeded suite.**  Decided: the
   accessory-time draw is made only when a branch can burn (section
   2.4) — the bare-hero path stays zero-draw, so every existing
   `SeqRng` test and the seed-42 draw-sequence test pass unmodified.
   Verify with the full suite.
2. **Faint duration 0.**  C: `nomul(-0)` is an instant no-op; the port
   sets `fainted = max(fainted, 10 - div)`, so a 0 duration blocks
   nothing — same observable behaviour.
3. **`uhunger` below the starvation floor while fainted.**  C's faint
   roll `rn2(20 - div)` is always well-formed (for h ≤ 0 the div is ≤
   0, so 20 − div ≥ 20); no clamp needed in the port.
4. **Hero base hunger 900 vs a test hero.**  The dataclass default is
   900 (the C start); test heroes that never tick hunger are
   unaffected.
