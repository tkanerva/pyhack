# `done/` — the plans that are finished

**Criterion for landing here:** the plan's *own* delivery scope is in the
tree and tested, and everything the plan still names as open belongs to a
*different* system's plan (a hand-off), not to this plan's own modules.
A plan with an unreached phase, an unpromised test or a stub in its own
`core/*.py` surface stays in the repo root.

Baseline when this folder was made: **1370 tests pass**, `mypy` clean
over 103 files, `flake8` clean.  (After the ring + erosion test suites
below: **1412 tests**, mypy over 105.  After the "genesis residue"
session: **1463 tests**, mypy over 106.)

| plan | landed as | tests |
|---|---|---|
| `PLAN-MKLEV.md` | `core/mklev.py`, `core/mkroom.py`, `core/mkmap.py`, `core/doors.py`, `new_world(generator=…)` | `test_mklev.py`, `test_mkroom.py`, `test_mkmap.py`, `test_worldgen_generators.py` |
| `PLAN-SPECIAL-ROOMS.md` | phases 0-5: `core/priest.py`, `core/engrave.py`, `core/shk.py`, `core/shknam_data.py`, `core.mkroom` (temple / zoo / swamp / shop pick / vault), `core.mklev` (vault + `makevtele`) | `test_priest.py`, `test_zoo.py`, `test_swamp.py`, `test_engrave.py`, `test_shop.py`, `test_vault.py` |
| `PLAN-EXPERIENCE.md` | `core/experience.py` + the `Monster` XP fields + the `apply_damage` kill hook + the status line | `test_experience.py` |

Named skips that are **not** residue: the `src/vault.c` guard and
`mk_knox_portal` (PLAN-SPECIAL-ROOMS.md), the themed-room Lua hook
(PLAN-SPLEV.md), the `mktrap` type table / `makeniche` treasure
(PLAN-MAKEMON.md §5-G, PLAN-MKOBJ.md phase G).

---

# What is still open (the 11 plans left in the repo root)

Ordered by "how much of it is already there". Each row names the concrete
residue, verified against the code, not just against the plan headers
(several headers are stale — PLAN-ARMOR.md and PLAN-INVENT.md understate
themselves, PLAN-EXPERIENCE.md's did, HUNGER's §5 predates the
occupation port).

| plan | state | what is actually left |
|---|---|---|
| **PLAN-INVENT.md** | phases A and B landed (the pack's single writer, stable letters, the stacking group) + phase F's display half (`core/invent.py`) | **B**'s last item is the **quantity in the messages** ("You pick up 3 arrows"), which is **C** naming (`core/objnam.py` — it replaces the reduced `invent.doname`), **D** weight / encumbrance (`weight_cap` / `inv_weight` / `near_capacity` / `ENC_STAT`; the pack is unbounded today), **E** gold (`findgold`, the leprechaun), **F** the menu half + `prinv`, **G** `getobj` / `select_many`, **H** `#adjust` |
| **PLAN-MKOBJ.md** | phases A-E in substance (`core/mkobj.py`), plus `splitobj` / `unsplitobj` and the container merge rules; the fire-trap regression test is `tests/test_erosion.py::test_fire_trap_erodes_the_worn_armour` | `mkobj_erosions`' rust / rot / corrode predicates, phase G's residue (the bonus item, the chest `!rn2(nroom*5/2)`, the graffiti — `make_engr_at` now exists) |
| **PLAN-MAKEMON.md** | phases A-E landed (383-row table, the funnel, `mkclass`, `newmonhp`, `peace_minded`, `mongets`, and the `initweap` / `initthrow` / `initinv` species kits) | **E**'s `m_dowear` (a monster's kit is carried, not worn — PLAN-ARMOR §5), **F** groups / `grow_up` / `clone_mon` / `create_critters`, `set_mimic_sym`, **G**'s trap-type table + `mktrap_victim` + the special-room fillers |
| **PLAN-ARMOR.md** | phases 1-4 landed and tested — phase 4's suite is `tests/test_erosion.py` (16 tests), which also caught the missing `Item.oerodeproof` | the per-type `<Type>_on()` / `<Type>_off()` side effects, still `NotImplementedError` in `core/worn.py` — `core/props.py` is the *query* half only |
| **PLAN-HUNGER.md** | the eat.c core is in (`core/hunger.py`: ticker, `uhs` machine, faint, choke, the multi-turn meal via `core/occupation.py`) | the `ATEMP` base/temp ability split (WEAK's −1 STR), the **encumbrance** decrement in `gethungry` + the "concentration falters" cast gate, tins, corpses / eggs, polyself nutrition, potion / fountain nutrition, the purple-worm swallow |
| **PLAN-RING.md** | phases 1, 2, 3 (regen + teleport) and 5 landed; discovery is real; phase 6's spec is in the tree as `tests/test_rings.py` (26 tests) | the active effects (levitation, stealth, invisibility / see-invisible, warning, the hunger drain, polymorph, conflict, accuracy / damage), ring **generation** in `mksobj`, the `ring_name` UI wiring |
| **PLAN-PICKUP.md** | only the 38-line `pickobj` subset (`core/pickup.py`: the top item on the tile, merging into the pack) | `pickup(ONE\|ALL)` + `g`/`,`, `lift_object` / `carry_count` / `encumber_msg`, the containers (`container_at`, `in_container`, `out_container`, `use_container`, `doloot`), `look_here` + the `:` command, autopickup, the menu selection (needs INVENT G), the hazard list as documented skips |
| **PLAN-DROP.md** | **not started** | no `DropCommand` / `WieldCommand` in `core/commands.py`; no `core/drop.py`, no `core/wield.py`; `Monster.wielded` is still a bare item id; `worn.count_worn_stuff` / `doddoremarm` (the `'A'` key) still raise |
| **PLAN-THROW.md** | **not started** (its prerequisites are all in: `splitobj` / `unsplitobj`, the merge rules, `stackobj`, the monster ammo kits) | no `core/throw.py`, `core/bhit.py`, `core/mthrowu.py`; still needs `occupation.stop_occupation` |
| **PLAN-BREATH.md** | **not started** | `core/zap.py` has the reduced `zap`, not `dobuzz` / `zap_hit` / `zhitm` / `zap_over_floor`; `mhitu` has no `AT_BREA` case |
| **PLAN-SPLEV.md** | **not started** | no `core/des.py`, `core/selection.py`, `core/mapfrag.py`, `core/splev.py`; no `dat/*.lua` level program ported |

## Suggested order (dependency-correct)

1. ~~**The test debt first**~~ — DONE: `tests/test_rings.py` (PLAN-RING.md
   phase 6) and `tests/test_erosion.py` (PLAN-ARMOR.md phase 4, plus the
   fire-trap regression PLAN-MKOBJ.md's DoD asked for) are in the tree,
   1412 tests green.  What is left of that item is nothing; the two
   plans' remaining entries are feature work (the ring effects and the
   `<Type>_on/off` side effects), listed in their own rows above.
2. ~~**The genesis residue** (PLAN-MKOBJ / PLAN-MAKEMON)~~ — DONE:
   `splitobj` / `unsplitobj`, the merge rules (`mergable` / `merged` /
   `merge_choice` / `stackobj` / `splittable`), the container and
   pickup merge points, and the `m_initweap` / `m_initthrow` /
   `m_initinv` species kits are in, with `tests/test_stacking.py` (49
   cases) and the re-pinned monster/shop/zoo suites; 1463 tests green.
   Leftovers, all owned by other rows: `m_dowear` (PLAN-ARMOR §5),
   monster groups (PLAN-MAKEMON F), the rust / rot / corrode erosion
   predicates (PLAN-MKOBJ), the muse.c item pickers.
3. **PLAN-THROW** (`dothrow.c` + `mthrowu.c` + `bhit`) — now first:
   every item primitive it needs (`splitobj`, `freeinv`,
   `place_object`, `stackobj`, `mergable` / `merged`) is in, and its
   phase 0 also lands `occupation.stop_occupation`, which
   PLAN-BREATH's `dobuzz` waits for.
4. **Wave 6: the pack** (PLAN-INVENT B's last item → C→E, then
   PLAN-PICKUP, then PLAN-DROP). Encumbrance (D) is what PLAN-HUNGER's
   ticker is waiting for; `objnam` (C) is what the pickup / drop / shop
   messages are waiting for.
5. **PLAN-BREATH** (`dobuzz`), which is the same beam engine the ray
   wands want.
6. **The scroll STUBs** (17 of `read.c`'s `seffects()` still raise) and
   `mmove()` — small, self-contained, and both are prerequisites for the
   special levels' feel.
7. **PLAN-SPLEV** last: it is the most parallelisable piece, but it needs
   `des.room` → `fill_special_room` and `des.object` → `mksobj` to be
   usable.

## Doc rot found while doing this (worth one cleanup commit)

- `ARCHITECTURE.md` queue item 4 ("wire `QuaffCommand`") is **done** —
  `ui/console.py` binds lowercase `q` to it.
- `ARCHITECTURE.md` "Also due": `nethack_index/tools/generate_index.py`
  has still not been rerun (the last commit message says so); `INDEX.md`
  keeps calling `mkroom.c` / `shknam.c` unported.
- `PLAN-EXPERIENCE.md`'s status header said "nothing implemented yet"
  (corrected in place here); `PLAN-ARMOR.md` and `PLAN-INVENT.md` also
  understate their landings in their first paragraph.
- `core/hunger.py`, `core/occupation.py` and `tests/test_hunger.py` cite
  a **`PLAN-OCCUPATION.md` that does not exist in the tree**. Either it
  was never written or it is missing from the clone.
- The three files archived here were **moved, not copied**: docstrings and
  docs that name them by name (`PLAN-SPECIAL-ROOMS.md phase 2`) still read
  fine, but a link that assumed the repo root will not resolve.
