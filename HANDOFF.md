# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.

This session executed the queue's **item 1's last piece: the test
debt** — the two systems that had landed as *code* with no test
pinning them: PLAN-RING.md phase 6 (a fully written 26-test spec for
`core/rings.py`, against a module that had no test file at all) and
PLAN-ARMOR.md phase 4 (erosion, whose only live call site is the fire
trap, and whose suite the plan itself recorded as "pending").  Both
suites are in the tree; nothing in either plan's *feature* list was
implemented, and no STUB was replaced.

## 2. Status
**Done (this session):**

- **`tests/test_rings.py` — 26 tests**, the phase-6 spec verbatim: the
  discovery contract (`ring_on` / `ring_off` are producers; the
  mutation happens only in `rules.apply_discovery` through
  `process_events`), the ability rings (computed, never cached —
  including the `uhitm` to-hit integration at the STR 12→17 threshold
  boundary), the protection ring's AC through `worn.uac` (left then
  right, doff restores, spe 0 discovers nothing), the two per-turn
  effects (`tick_rings`: the silent regen, the 1-in-85 teleport) with
  the draw audit (a ring-less hero draws ZERO; a worn teleport ring
  draws exactly one), the passive rings (prop conveyance through
  `core.props`) and the feel-it rings (type discovered on wear, no
  active state toggled), `ring_name` (bare `"ring"` / `"ring of X"` /
  the `(+N)` of a charged *known* ring), the `_type_on` / `_type_off`
  dispatch, `dowear` applying the discovery (the `DiscoveryEvent` is
  consumed, not returned), the `step()` Wear/TakeOff round trip, and
  the "an unworn ring costs no rng draws" determinism guard.
- **`tests/test_erosion.py` — 16 tests**, PLAN-ARMOR.md phase 4: the
  material predicates over real rows, `erosion_matters` /
  `obj_erode_type` (C's burn → rust → crack priority), `erode_obj`'s
  primary (`oeroded`) and secondary (`oeroded2`) counters with the
  full message ladder (plain / further / completely), the grease
  protection with its 1/2 wear-off, the blessed 1/4 resistance,
  `oerodeproof`, the `EF_DESTROY` destruction (worn slot cleared, item
  gone, crystal armour `shatters`), the AC following for free
  (`arm_bonus` / `uac`), the two live call sites (`burnarmor` from the
  fire trap, `erode_armor` from the acid passive), the destroy-armour
  scroll's `disintegrate_arm` (C's cloak → suit → … order) /
  `destroy_arm` (the 1..4 hits, stopping at a destruction), and
  `mkobj_erosions`' erodeproof roll.
- **A real bug, found by the erosion suite:** `Item` had `oeroded` /
  `oeroded2` but **no `oerodeproof`**, which `worn.erode_obj` reads
  unconditionally (line 814) and `destroy_arm` tests (line 996) — so a
  **fire trap on a hero in worn armour raised `AttributeError`**.  It
  is the exact defect class PLAN-MKOBJ.md §2 recorded for `oeroded`,
  one field short, and the plan's phase-4 item 1 had specified the
  third field.  Fixed: `Item.oerodeproof: bool = False` (C
  `obj->oerodeproof`), and `core.mkobj.mkobj_erosions` now sets it on
  C's `!rn2(100)` roll instead of returning bare (the roll was already
  taken, so no draw moved).
- **Baseline: 1370 → 1412 tests green**, `mypy` clean over 105 files
  (the 2 new test modules), `flake8` clean, `black` clean.
- Docs in the same commit: this HANDOFF, CHANGES.md ("The test debt"),
  PLAN-RING.md (phase 6 ✅ + the execution order), PLAN-ARMOR.md (the
  status header + phase 4's items 1 and 4), PLAN-MKOBJ.md (the DoD
  checkbox + the §2 defect row), `done/README.md` (the two plan rows
  and "the test debt first" struck), ARCHITECTURE.md (the ARMOR /
  RINGS bullets and the queue's item 2).

**Not done:** no feature work.  In particular the ring *effects*
(levitation, stealth, invisibility / see-invisible, warning, the
hunger drain, polymorph, conflict, accuracy / damage) are still STUBs,
ring **generation** (the `mksobj` RING branch) is still open, and the
`<Type>_on()` / `<Type>_off()` armour side effects still raise
`NotImplementedError` — all three are their listed systems' work
(PLAN-RING.md's deferred list, PLAN-ARMOR.md phase 5), not test debt.

## 3. Files to read first
1. `done/README.md` — the remaining-work table (now with the two test
   suites recorded) and the dependency-correct order; the row for the
   plan you pick is the summary of what is actually left.
2. `tests/test_rings.py` and `tests/test_erosion.py` — the two new
   suites, and the conventions they pin (the `_ring` / `_item`
   builders over the REAL `OBJECTS` rows, `SeqRng` for the exact
   branch, the `CountingRng` / `CountingRandom` draw audits).
3. `core/rings.py` (its module docstring is the STUB map) and the
   erosion block of `core/worn.py` (line ~572-1005).
4. `ARCHITECTURE.md`'s "Suggested next steps" — items 2-8 are the
   queue; item 1 is now complete.

## 4. Key discoveries
- **The `Item` field set has a habit of landing one field short.**
  `oeroded` landed with PLAN-MKOBJ phase A while `oerodeproof` did
  not, and nothing noticed because `erode_obj`'s call sites are only
  reached by a *live* fire trap on a *geared* hero.  When a plan lists
  fields in one item, grep the readers (`item.oeroded`,
  `item.oerodeproof`, …) against `core/types.py` before writing any
  test — the missing one is a one-line fix that a test makes permanent.
- **The ring spec's §22 was wrong; the port is right.**  The plan said
  an undiscovered ring "resolves through the (possibly shuffled)
  description"; `ring_name` returns the bare `"ring"` and never leaks
  the description (C's xname behaviour for an unidentified ring).  The
  test pins the port and the plan records the deviation.
- **The draw audits are cheap and worth copying.**  `tick_rings` reads
  `worn_properties(mon)` first and only rolls the teleport check when
  the prop is actually worn, so a ring-less hero costs zero draws;
  `test_tick_rings_draws_only_when_needed` and
  `test_an_unworn_ring_costs_no_draws` are the pattern for any new
  per-turn effect (the hunger port's decision 4 does the same thing).
- **`Random`-backed counting is enough for `step()`.**  The step-level
  determinism test wraps `random.Random` in a `randint` / `choice` /
  `shuffle` counter rather than pre-loading a `SeqRng` — step touches
  too many branches for a preset list.
- **`erode_obj`'s message vocabulary is data** (`_ERODE_ACTION` /
  `_ERODE_MSG` / `_ERODE_BYTHE`), and `_ERODE_BYTHE` is used without
  an article ("not affected by heat"), which is what C's `bythe[]`
  does.  Copy the strings from the table, not from memory.
- The pytest tool's `paths` still resolve to a container mount that
  does not see the files; run the full suite with no `paths` and use
  `keyword` for a slice.

## 5. Next steps
1. **The queue moves to item 2 — the genesis residue** (independent of
   everything else, and it unblocks four plans at once): `splitobj` /
   `unsplitobj` (PLAN-MKOBJ §3.6 defers them to PLAN-THROW, but
   PLAN-INVENT phase B's `splittable` and PLAN-PICKUP / PLAN-DROP need
   them too — land them with the merge rules), the container merge
   rules, and `m_initweap` / `m_initinv` (PLAN-MAKEMON phase E) for
   real monster inventories.
2. **Then Wave 6, the pack** (PLAN-INVENT B→E → PLAN-PICKUP →
   PLAN-DROP): encumbrance (D) is what PLAN-HUNGER's ticker waits for,
   and `core/objnam.py` (C) is what every pickup / drop / shop message
   waits for.
3. **Then PLAN-THROW** (`dothrow.c` + `mthrowu.c` + `core/bhit.py`),
   whose phase 0 also lands `occupation.stop_occupation` (PLAN-BREATH
   needs it too), then **PLAN-BREATH** (`dobuzz`).
4. Small items that can interleave: the 17 remaining `read.c`
   `seffects()` STUBs (SCR_DESTROY_ARMOR now has its machinery *and*
   its tests — `disintegrate_arm` / `destroy_arm` are covered), the
   full `mmove()` (monsters still cannot open doors), and ARCHITECTURE
   queue item 4's stale "wire `QuaffCommand`" entry (already done).
5. Keep this file updated per the 5 sections; keep every PLAN status
   header and `done/README.md`'s table in sync in the same commit.
