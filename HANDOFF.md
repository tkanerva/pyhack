# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.

This session executed the queue's **item 2 — the genesis residue**:
the three pieces the earlier waves named and left open, which between
them unblock four plans.  Nothing in PLAN-INVENT.md phase B's or
PLAN-MAKEMON.md phase E's *deferred* lists was touched.

## 2. Status
**Done (this session):**

- **The stacking group, `core/invent.py`** (PLAN-INVENT.md phase B):
  `mergable` (C 4429-4551, the whole rule table minus the halves whose
  systems do not exist), `merge_choice` (771-810, including the "punt"
  on a scroll of scare monster), `merged` (812-948: the quantity sum,
  the `owt` recompute, the quantity-weighted age, the worn-slot
  preference, the compare-to-learn `known`, and `delobj` for the
  loser), `stackobj` (4415-4427) and `splittable` (1662-1668).
  `addinv` now merges on the way in (the C `merged(&otmp, &obj)` walk
  down the chain), so a second dagger is `quan == 2`, not a second
  item.
- **The split pair, `core/mkobj.py`** (PLAN-MKOBJ §3.6, deferred there
  to PLAN-THROW): `splitobj` / `unsplitobj` (mkobj.c 456-503,
  555-622), with the `(parent, child)` record on `World.split_parent` /
  `split_child` (C's one-slot `svc.context.objsplit`).
  `add_to_container` is now the second merge point (a chest's two
  identical daggers are one stack) and returns the survivor.
- **The species kits, `core/makemon.py`** (PLAN-MAKEMON.md phase E):
  `initweap` (C's 413-line `switch (ptr->mlet)`, 160-572, draw for
  draw), `initthrow` (`rn1(oquan, 3)` in one stack) and `initinv`
  (588-833: the mercenary AC ladder, the shopkeeper / priest / monk /
  nymph / giant / leprechaun / gnome / lich / nazgul / quantmech kits
  and the two tails).  A BARRACKS squad now carries swords and armour
  and a leprechaun carries gold — phase E's exit check.
- **Three defects the change surfaced, all fixed:** `mongets` answered
  the id of an object the merge could delete (it answers the stack
  now); `pickup` messaged and **billed** the floor object after
  `addinv` had possibly merged it away (it bills the survivor); and
  `add_to_container` answered None.
- **`tests/test_stacking.py` — 50 cases**, the suite the two systems
  had none of: every row of the merge table on its own field, the coin
  shortcut, `oc_merge`, the revivable corpse, the candle window, the
  `merge_choice` punt, `merged`'s quan / weight / age / worn slot /
  discovery, `stackobj`, `splittable`, the split round trip and its
  four refusals, and both merge points.  Plus the pickup-merges case
  in `test_pickup.py`.
- **Baseline: 1412 → 1463 tests green**, `mypy` clean over 106 files,
  `flake8` clean, `black` clean.
- Docs in the same commit: this HANDOFF, CHANGES.md ("The genesis
  residue"), PLAN-INVENT.md (phase B ✅ + the DoD box), PLAN-MKOBJ.md
  (§3.6 / §6 / the function table / the status header), PLAN-MAKEMON.md
  (phase E ✅ + the status header), PLAN-THROW.md (the splitobj rows),
  PLAN-PICKUP.md / PLAN-DROP.md (the dependency rows), ARCHITECTURE.md
  (the queue and the two "still open" bullet lists).

**Not done:** `m_initgrp` / `m_initsgrp` / `m_initlgrp` (monster
groups) are PLAN-MAKEMON phase F; `m_dowear` — the monster putting its
armour on — is PLAN-ARMOR §5's, so a monster's kit does not yet change
its AC; the muse.c item pickers (`rnd_offensive_item` /
`rnd_defensive_item` / `rnd_misc_item`) are unported, and their rolls
are taken with the branch named (the draw-order rule).  Nothing calls
`stackobj` or `unsplitobj` yet: the drop and the throw landing
(PLAN-DROP / PLAN-THROW) are their callers.

## 3. Files to read first
1. `done/README.md` — the remaining-work table and the
   dependency-correct order; the row for the plan you pick is the
   summary of what is actually left.
2. `tests/test_stacking.py` — the conventions this session pinned: the
   hand-built item over a REAL `OBJECTS` row (`_item`), why mksobj is
   *not* used for a rule test, and `assert_item_locations` after every
   mutation.
3. `core/invent.py`'s stacking block (line ~394-640) and
   `core/mkobj.py`'s split block (line ~725-830) — the two docstrings
   carry the whole C mapping and the three documented divergences.
4. `core/makemon.py`'s `initweap` / `initinv` (line ~1150-1900) — the
   kit port, its `_KIT_SPECIES` / `_SCHOLAR_GUARDIANS` tables (which
   resolve every species name at import, so a typo fails the import
   rather than a generated level) and the named skips.
5. `ARCHITECTURE.md`'s "Suggested next steps" — item 3 is the queue
   now (PLAN-THROW / PLAN-BREATH), item 2 is done.

## 4. Key discoveries
- **A merge deleted the second writer's idea of "the item".** Two call
  sites (`makemon.mongets`, `pickup`) used the object they had just
  handed to `addinv` *after* the call; once `addinv` merges, that
  object can be gone.  Whenever a function starts merging, grep its
  callers for use-after-add: C leaks the same dangling pointer in
  `mongets`, so "C does it too" is not a defence — the port answers the
  survivor.
- **`add_to_container` already had the merge hook's shape** (a
  `for child in contents` loop that could call `merged`), which is why
  the container half of phase E cost three lines.  The C `add_to_minv`
  / `add_to_container` pair is one behaviour in two places; pyhack has
  it in `addinv` and `add_to_container` and nowhere else.
- **The generated levels change when monsters get kits, and four
  suites pinned generated content.** The fix was never a new seed: the
  zoo / leprehall / court / morgue tests were reading
  `World.items` and a monster's kit lives there too (`lev` is the
  monster's level), so they now read *floor* items
  (`pos is not None`); the jewellery-shop test had declared C's
  `rn2(2)` charging scroll unconditional; the morgue's chest roll now
  spans three seeds.  Each edit says which.
- **`is_reviver` in this port is `is_rider || S_TROLL`** (C's macro),
  so a troll corpse is the test case for "a revivable corpse never
  merges" — a zombie is not.
- **The pytest tool's `paths` still resolve to a container mount that
  does not see the files**; run the full suite with no `paths` and use
  `keyword` for a slice.
- **`black` was not run over the previous session's `core/makemon.py`**;
  it reformatted on the first run this session (`tests/test_stacking.py`
  the same).  Run black on every touched file before committing.

## 5. Next steps
1. **The queue moves to item 3 — PLAN-THROW** (`dothrow.c` +
   `mthrowu.c` + `core/bhit.py`).  `splitobj` / `unsplitobj`,
   `mergable` / `merged` and `stackobj` all landed for it: the volley
   loop (`splitobj` → `freeinv` → `throwit`) and `drop_throw`'s
   landing (`place_object` → `stackobj`) now have every primitive they
   need.  Phase 0 also lands `occupation.stop_occupation`, which
   PLAN-BREATH's `dobuzz` waits for.
2. **Then Wave 6, the pack** (PLAN-INVENT B→E → PLAN-PICKUP →
   PLAN-DROP): phase B's own remaining items are the **quantity wording**
   in the messages ("You pick up 3 arrows") which needs phase C's
   `core/objnam.py`, and phase C is what every pickup / drop / shop
   message waits for; encumbrance (D) is what PLAN-HUNGER's ticker
   waits for.
3. **Then PLAN-BREATH** (`dobuzz`), which is also the first real user
   of the ray code.
4. Small items that can interleave: the 17 remaining `read.c`
   `seffects()` STUBs, the full `mmove()` (monsters still cannot open
   doors), PLAN-MAKEMON phase F's monster groups, `m_dowear` (which
   would make a soldier's mail mean something), and ARCHITECTURE queue
   item 4's stale "wire `QuaffCommand`" entry (already done).
5. Keep this file updated per the 5 sections; keep every PLAN status
   header and `done/README.md`'s table in sync in the same commit.
