# Changes: scroll system (the read.c port)

Pending git push.  Summary of the working-tree state as of this change:
the demo game now has scroll reading — the first five effects of C's
`seffects()` switch (src/read.c) are implemented and tested, the
remaining seventeen C handlers are STUBs that raise loudly, and the
demo floor carries one of each implemented scroll.

Ground truth is the NetHack 5.0 C source (local clone at `../NetHack`):
`src/read.c` (`doread`, `seffects`, `seffect_*`), `src/wield.c`
(`chwepon`), `src/do_wear.c` (`some_armor`), `src/mkobj.c` (`uncurse`),
`src/teleport.c` (`scrolltele`), `src/potion.c` (`strange_feeling`).

## Scope (deliberate)

Only the small subset the user picked for the initial port:

| scroll            | C handler                      | state      |
|-------------------|--------------------------------|------------|
| blank paper       | `seffect_blank_paper`          | implemented |
| enchant weapon    | `seffect_enchant_weapon` + `chwepon` | implemented |
| enchant armor     | `seffect_enchant_armor` + `some_armor` | implemented |
| remove curse      | `seffect_remove_curse` (unconfused branch) | implemented |
| teleportation     | `seffect_teleportation` -> `scrolltele` | implemented |
| the other 17      | `seffect_destroy_armor`, `seffect_confuse_monster`, `seffect_scare_monster`, `seffect_create_monster`, `seffect_taming`, `seffect_genocide`, `seffect_light`, `seffect_charging`, `seffect_amnesia`, `seffect_fire`, `seffect_earth`, `seffect_punishment`, `seffect_stinking_cloud`, `seffect_gold_detection`, `seffect_food_detection`, `seffect_identify`, `seffect_magic_mapping` | **STUB** (`NotImplementedError`) |

## Files changed

| file | change |
|---|---|
| `core/types.py` | **`ScrollType` enum** — all 22 `SCR_*` types a non-MAIL build knows (C order, SCR_MAIL compiled out as in `core.objects`); **`Item.scroll_type`** field (next to `potion_type` / `spell_type`) |
| `core/commands.py` | **`ReadCommand(item_id)`** (C: 'R'/'r' — doread) + the `Command` union |
| `core/scrolls.py` | **new** — `read_scroll(world, monster_id, item_id, rng)`, the five `seffect_*` handlers above, `some_armor` (C do_wear.c) and `_chwepon` (C wield.c) as module functions; the STUB dispatch for the unported handlers; `SPE_LIM = 99` (C objclass.h), `_cap_spe` (C cap_spe) |
| `core/step.py` | wire `ReadCommand` into the player turn (the same `was_asleep` gate as quaff / cast / wear / pickup) |
| `core/worldgen.py` | **`FLOOR_SCROLLS`** — five floor scrolls at FIXED positions (`(17,7)` enchant weapon, `(23,7)` enchant armor, `(17,13)` remove curse, `(23,13)` teleportation, `(20,12)` blank paper), reserved via `generate_map(keep_floor=...)` like `FLOOR_ARMOR` |
| `ui/console.py` | `r<letter>` key -> `ReadCommand` (the `w/t` two-key handler extended with `r`) |
| `main.py` | banner: the `r<letter>` key + a scroll hint |
| `core/__init__.py` | export `ScrollType`, `ReadCommand` |
| `tests/test_scroll.py` | **new** — 21 tests, table-driven over the C branches with `SeqRng` |
| `tests/test_worldgen.py` | `test_floor_scrolls_lies_on_floor_tiles` (fixed positions, fine identity, effect tag, no carrier) |
| `README.md` | layout list + keys + demo scroll note |
| `ARCHITECTURE.md` | diagram, the behaviour-decision bullets, suggested next steps |
| `CHANGES.md` | this file |

No other files changed; `core/worn.py`, `core/mhitu.py`, `core/uhitm.py`
and the rest of the suite are untouched.

## Design decisions (kept consistent with the house rules)

1. **One command, one entry point.** `ReadCommand(item_id)` ->
   `step()` -> `read_scroll()`, exactly the `QuaffCommand` /
   `CastCommand` pattern.  Pure function over `World`, events out,
   injected `rng`.
2. **`Item.scroll_type` is the effect tag** (the C `sobj->otyp` of the
   `seffects()` switch), parallel to `Item.potion_type` /
   `Item.spell_type`.  The fine identity (`otyp` / `oclass` over
   `core.objects.OBJECTS`) is set on the demo scrolls too, so the
   enchant effects' table lookups (`row.magic`) run on the real rows.
3. **Consume-after-effect, blank paper excepted** — C's `doread`:
   `if (otyp != SCR_BLANK_PAPER) useup(scroll)`.  Reading consumes one
   turn (consistent with quaff / cast; failed reads included, the
   house rule).
4. **Draw-order discipline.** Every rng draw is an inline
   `rng.randint(1, n)` at the C `rn2(n)` / `rnd(n)` site with a
   comment; C's truncating integer division is reproduced with
   `int(x / y)` (Python's `//` floors and would diverge for negative
   spe).  A scroll whose effect branch draws nothing draws nothing —
   SeqRng tests pin the C branches one for one (e.g. the plain +1
   enchant is a zero-draw path, like the Phase-1 `AC_VALUE` rule).
5. **C-faithful details kept because they are cheap and testable:**
   - the `some_armor` slot order with the 3/4 (`!rn2(4)`) takeover
     draws, each draw only when an earlier slot was already selected;
   - the elven vibration/evaporate warning (`elven 5, else 3` limit,
     `rn2(s) != 0` evaporate, slot cleared + armor consumed);
   - the base power `(4 - s)/2` + elven +1 / nonmagical +1 / blessed
     +1, the rare `!rn2(spe)` +1, the cap 11, the sign flip for a
     cursed scroll;
   - the enchant-weapon amount formula verbatim (cursed -1, spe >= 9
     -> 0-or-1, blessed `rnd(3 - spe/3)`, else 1) and `chwepon`'s soft
     +/-5 evaporate limit (2/3), positive-enchant uncurse, and the
     high-spe vibration clue (elven short-circuits the `!rn2(7)` draw,
     as C does);
   - the armor BUC transfer (cursed scroll curses the armor, blessed
     blesses, an uncursed scroll uncurses) — and, matching C, the
     weapon gets NO such transfer (only the positive uncurse);
   - remove curse: a cursed scroll only disintegrates (the
     `nodisappear` "You read the scroll." line); an uncursed scroll
     only touches WORN items (the `wornmask` condition), a blessed one
     the whole pack; uncurse is silent (C's `uncurse()` emits nothing
     for inventory items); the scroll hides itself from its own scan.
   - the "As you read the scroll, it disappears." line precedes the
     effect, as in C's `doread`.
6. **Demo integration without touching the seeded game.** The five
   floor scrolls sit at fixed positions reserved through
   `generate_map(keep_floor=...)` — **zero rng draws** (the
   `test_new_world_makes_no_new_rng_draws` draw-sequence test passes
   unmodified), so the seed-42 layout, trap / monster placement and
   every seeded test are byte-for-byte untouched.  The cursed cloak
   (`FLOOR_ARMOR`) pairs with the remove curse scroll: it cannot be
   taken off (`dotakeoff` blocks cursed gear) until the scroll frees
   it.

## Documented simplifications (not bugs)

- No blind / confused / hallucinating reader variants: the demo hero
  has no such status path; C's alternate-outcome branches (confused
  armor/weapon `oerodeproof` flip, confused remove-curse
  `blessorcurse`, the cursed-teleport level teleport, ...) are
  dropped, as is the `level_tele` / same-level distinction (the demo
  is single-level) and the blessed teleport's `getpos` destination
  (no prompt machinery mid-step) — both collapse to the plain random
  teleport on the floor-tile set.
- No conduct / livelog / discovery bookkeeping (`makeknown` /
  `exercise` / `trycall`); demo items are fully known.
- Enchant weapon: the worm-tooth <-> crysknife transformation, the
  cursed tin-opener weld branch, the artifact / magicbane clues are
  dropped (none is in the demo).  Enchant armor: the dragon-scales ->
  scale-mail merge is dropped (no dragon scales in the demo).
- The elven test is by table name ("elven ..."): the ported `Object`
  row carries no C `OC_ELVEN` flag; the test is exact over the demo's
  elven subset.  (C 5.0 quirk preserved: the elven mithril coat and
  elven leather helm rows are NOT `oc_magic`, so they take BOTH the
  elven and the nonmagical power bonus.)
- The `W_WEP` bit in the remove-curse worn mask is never set in
  pyhack (wielding stays on `Monster.wielded`, PLAN-ARMOR.md
  decision 8); it is included for C fidelity.

## Stubs

The unported handlers are one dispatch STUB in `core/scrolls.py`
(`read_scroll`'s `else` branch) rather than seventeen empty
functions: it raises `NotImplementedError` naming the scroll and its
C provenance (`src/read.c seffects()`), so a future demo scroll of an
unported type fails loudly instead of silently doing nothing (the
house STUB convention, cf. `worn.py`).  `worn.disintegrate_arm` /
`destroy_arm` (the Phase-4 destroy-armor fills) are real and tested
and now have a named awaiting call site: the `SCR_DESTROY_ARMOR`
stub, per the PLAN-ARMOR.md note.

## Tests

`pytest` from the repo root.  New: `tests/test_scroll.py` (21 tests)
covering, per effect, the C branches with exact `SeqRng` draws:

- doread plumbing: find / floor / untyped rejection, blank paper not
  consumed, the "you read" line, the STUB raise;
- enchant weapon: no weapon (twitch / itch), flat +1 (zero draws),
  blessed `rnd(3)`, cursed -1 (no curse transfer), spe >= 9 violent
  no-change glow (evaporate + vibration draws audited negative),
  evaporate past the soft limit (wielded slot empties);
- enchant armor: no armor ("Your skin glows then fades."), chain
  `rnd(3)`, blessed `rnd(4)` + bless transfer, cursed disenchants +
  curses, elven evaporate (slot cleared, armor consumed), elven
  spe 8 violent no-change + the elven vibration clue, helmet takeover
  by roll (some_armor's 3/4 swap);
- remove curse: worn uncursed, carried ignored (uncursed scroll),
  carried uncursed (blessed scroll), cursed scroll disintegrates;
- teleportation: floor-tile move; `step()` wiring (turn, consumption,
  events).

`tests/test_worldgen.py` gains the floor-scrolls placement test; the
existing suite (incl. the seed-42 determinism and draw-sequence tests)
is expected to pass unmodified — the change adds no rng draw to
`new_world`.

## Suggested commit sequence (house style: one commit per task)

1. `types/commands: ScrollType enum, Item.scroll_type, ReadCommand`
   (core/types.py, core/commands.py, core/__init__.py)
2. `scrolls: the read.c port -- five seffect_* + STUBs`
   (core/scrolls.py, core/step.py)
3. `demo: five floor scrolls (fixed positions, no rng draws) + the r<letter> key`
   (core/worldgen.py, ui/console.py, main.py)
4. `tests: test_scroll.py + the worldgen floor-scrolls test`
   (tests/test_scroll.py, tests/test_worldgen.py)
5. `docs: README / ARCHITECTURE / CHANGES for the scroll port`
   (README.md, ARCHITECTURE.md, CHANGES.md)
