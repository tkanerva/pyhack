# Plan: Wave 6b — pickup and containers (`src/pickup.c`)

**Status: proposed, nothing implemented.** Second of the three Wave 6
documents; it assumes PLAN-INVENT.md's model (`quan`, `owt`, `invlet`,
`contents`, `carrier`) and its `core/invent.py` location functions
(`addinv` / `freeinv` / `useup` / `delobj` / `place_object`). Nothing
here is implementable before PLAN-INVENT phase A lands.

**Goal:** `core/pickup.py` grows from its 14-line `pickobj` subset into
the port of `src/pickup.c`: taking things off the floor and failing
when the pack is too heavy, stacks, containers (put in / take out /
look inside), autopickup, and `look_here` — the "You see here a
scroll" half of looking at the floor.

**Ground truth:** `../NetHack` through `nethack_index`
(`INDEX.md` row `src/pickup.c`: 4,116 lines, 40k tokens, 68 functions;
pyhack coverage **2%**, size ratio 0.01× — i.e. the module is 1% of the
C file it cites; `symbols/pickup.json` has the spans).
`PROGRESS.index.md` §11.28 is prose and drifts (it calls `pickup.c`
"~2800 lines" and invents a `PickupSystem` class).

---

## 1. What the C code does (reference)

| group | C function (`src/pickup.c` unless noted) | span | what it does | port target |
|---|---|---|---|---|
| **entry** | `pickup(what)` | 671-910 | `what < 0` = "one of these", `what == 0` = "everything here" (`g` vs `,`); the swallow / pool / lava / levitation / pit gates; the per-square loop | `pickup.pickup` |
| | `pick_obj(otmp)` | 1900-1946 | one square's item: is it really here, is it the ball's chain, is it already carried → hand off | `pickup.pick_obj` |
| | `pickup_object(obj, count, tk)` | 1806-1892 | `observe_object`, the engulfed-worn case, the corpse/artifact refusals, the scare-monster scroll special case, `carry_count`, `obj_extract_self` + `addinv` | `pickup.pickup_object` |
| **capacity** | `lift_object` | 1708-1799 | "can this be lifted at all?" — the loadstone/boulder override, the 52-letter limit, then delegates to `carry_count` | `pickup.lift_object` |
| | `carry_count` | 1573-1705 | "how many of them can I carry?" — the weight projection, the gold arithmetic, the partial-stack messages | `pickup.carry_count` |
| | `delta_cwt` | 1547-1570 | the container weight delta when moving something in or out | `pickup.delta_cwt` |
| | `encumber_msg` | 1981-2024 | "You are now burdened / stressed / …" after a capacity change | `pickup.encumber_msg` |
| **containers** | `container_at(x, y, dir)` | 2027-2042 | which container is at / next to a square | `pickup.container_at` |
| | `able_to_loot(x, y, verb)` | 2044-2073 | can the hero reach it (swallowed / levitating / pit / underwater) | `pickup.able_to_loot` |
| | `stash_ok` / `u_handsy` | 2963-2976 / 2949-2960 | "is this a container you can put things in" / "do you have a free hand" | `pickup.stash_ok`, `pickup.u_handsy` |
| | `in_container(obj)` | 2564-2719 | take things out (the big one: 155 lines) | `pickup.in_container` |
| | `out_container(obj)` | 2733-2784 | put things in | `pickup.out_container` |
| | `use_container(container, held, more, verb)` | 2978-3233 | the (a) put in / (b) take out / (c) look / (d) tip menu | `pickup.use_container` |
| | `do_loot_cont` / `doloot` / `doloot_core` | 2091-2166 / 2169-2178 / 2181-2353 | `#loot` in a direction: find the box on the floor, reach it, choose in/out/both | `pickup.doloot` |
| | `loot_mon` | 2437-2488 | loot a *monster's* pack (needs `mon.c` `minvent`) | deferred |
| | `dotip` / `tipcontainer` / `choose_tip_container_menu` | 3571-3866 | `#tip`: empty a container onto the floor | deferred (§5) |
| | `observe_quantum_cat`, `container_gone`, `mbag_explodes`, `do_boh_explosion`, `boh_loss`, `mbag_item_gone`, `removed_from_icebox` | 2494-2976 | bag-of-holding laws, the boxed cat, ice boxes | deferred (§5) |
| **autopickup** | `autopick_testobj` | 929-965 | does this object match `flags.pickup_types` (and the exception list) | `pickup.autopick_testobj` |
| | `autopick` | 974-1003 | the loop over the square after a move | `pickup.autopick` |
| | `check_autopickup_exceptions` | 912-927 | the `.nethackrc` `AUTOPICKUP_EXCEPTION` list | deferred (`options.c`) |
| **looking** | `simple_look` | 75-98 | the one-item version | `pickup.simple_look` |
| | `check_here` / `n_or_more` / `menu_class_present` | 429-472 | "You see here 3 items" bookkeeping | `pickup.check_here` |
| | `force_decor` / `deferred_decor` / `describe_decor` | 316-426 | the drawbridge / altar / fountain / sink / grave / trap description of a square | subset (§5) |
| | `query_objlist` / `query_category` / `count_categories` | 1024-1220 / 1229-1512 / 1514-1540 | the multi-select menus both the loot and the drop paths use | PLAN-INVENT phase G |
| **outside the file** | `invent.c look_here` / `dolook` | 4149-4367 / 4370-4383 | the `:` / `;` commands: "You see here …" | `pickup.look_here` |
| | `invent.c loot_classify` / `loot_xname` | 148-305 / 308-387 | the classification both menus share | PLAN-INVENT phase G |

Data and machinery that already exists:

- `World.items_at(pos)` — the floor pile on the *current* level, in
  insertion order (the C `nexthere` chain, read backwards); `pickup`
  already uses `here[-1]` as "topmost".
- `invent.addinv` / `freeinv` / `useup` (PLAN-INVENT phase A) — the
  only writers of location.
- `invent.mergable` / `merged` (phase B) — stacking.
- `hacklib.distmin`, the direction prompt in `ui/console.py`, and the
  `TerrainType` predicates (`is_pool`, `is_furniture`, …) for the
  gates.
- `Item.dknown` + `rules.apply_discovery` — `observe_object`'s half of
  "you now recognise this scroll".

---

## 2. Where pyhack stands

`core/pickup.py` is 38 lines of code. Its whole body:

```python
here = world.items_at(mon.pos)
if not here:
    return [MessageEvent("You see nothing here to pick up.")]
top = here[-1]
top.pos = None
top.container = mon_id
mon.inventory.append(top)
return [MessageEvent(f"You pick up the {top.name}.")]
```

and its documented simplifications say exactly what is missing: *no
merging, no `INV_MAX` cap, no leashes / containers / food checks*. What
that costs:

| missing | what the player sees today |
|---|---|
| capacity | the pack is infinite; `Item.owt` has no reader; `near_capacity` does not exist |
| merging | picking up a second arrow gives two lettered items called "arrow" |
| containers | a chest would be a single opaque object; `loot`/`tip`/put-in do not exist |
| `,` (pick up everything) | each item on the square needs its own turn |
| `look_here` | walking over a scroll says nothing; you must pick it up to find out what it is |
| autopickup | gold must be picked up by hand (and gold does not exist yet) |
| the gates | the hero can pick things up while swallowed / levitating / standing in a pool |

The four gates C spends 120 lines on are not hypothetical: `step.py`
already has `is_stuck` and the door/stair commands, `worn.py` has a
`greased` flag, and PLAN-MAKEMON adds monsters whose engulf attack is
`u.uswallow`. None of them is reachable *today* — which is precisely
why the port order below puts the gates after the mechanics.

---

## 3. Design decisions

1. **`pickup(world, mon_id, rng, what=ALL)` keeps one entry point**,
   with C's `what` argument: `what == ONE` ("g", the topmost item) and
   `what == ALL` (",", everything on the square, in `world.items_at`
   order). `Command` gains `PickupCommand(all: bool = False)`; `g`
   keeps its current meaning, so the four existing pickup tests keep
   passing.
2. **Capacity is a projection, not a check.** `carry_count` asks
   `invent.calc_capacity(mon, item.owt)` — "what would my encumbrance
   level be *if* I carried this" — and answers "all of them / some of
   them / none of them". There is no "current weight" variable; the
   same computation runs before the pickup and after it for
   `encumber_msg`. This is why PLAN-INVENT decision 6 (computed, never
   cached) matters here: a pickup that merges into a worn-adjacent stack
   cannot leave the reported burden stale.
3. **A partial pickup splits the stack** (`quan -= n`, `owt` recomputed)
   and reports it — "You can only lift some of the 20 arrows lying
   here." C's message set (pickup.c 1680-1700's four prefixes) is
   ported verbatim; the "you cannot lift any more" branch is the one
   that must *not* consume the item.
4. **Containers are `Item.contents: List[str]`, and the *data*
   functions are PLAN-MKOBJ's.** `add_to_container` /
   `delete_contents` / `weight` recursion / `mkbox_cnts` land there
   (its phase E); this plan owns the **player-facing** in/out
   (`in_container` / `out_container` / `use_container` / `doloot`).
   The invariant: a contained item has `pos is None`, `carrier is None`,
   and its id appears in exactly one parent's `contents`.
5. **The loot menu becomes a two-step console flow, not a cursor
   menu.** C shows in/out/tip as a `yn`-style menu (`in_or_out_menu`);
   the console has no menu widget. `l<letter>` on a carried container,
   or `l` + a direction on a floor container, asks
   `take out / put in / look (t/p/l)`, and the two selecting arms reuse
   PLAN-INVENT's `select_many` (C `query_objlist`). The *menu data*
   (`loot_classify` / `loot_xname`) is invent's; the *keystrokes* are the
   UI's.
6. **`#loot` and `,`/`g` both work on a floor container.** C's
   `doloot_core` looks at the square *and* the eight neighbours
   (`container_at` with a direction); pyhack's version takes a
   direction for the neighbour case and the hero's own square without
   one.
7. **Autopickup is a `World` field, defaulting to gold only.** C's
   `flags.pickup` defaults on with `flags.pickup_types = "$"`. The demo
   has no gold, so turning it on changes no pinned test; when PLAN-MKOBJ
   phase D puts gold on the floor, walking over it must pick it up
   silently (`"You pickup 27 gold pieces."`). Exception lists are
   `options.c` (§5).
8. **`look_here` runs after a move, C's way, and that is the one
   behaviour change to audit.** `step._do_move` gains a `look_here(0)`
   call after a successful step (C: the `domove` / `moveloop` hook).
   It only emits text when the destination holds an item and the hero
   can see it; the audit is "which existing test walks the hero onto a
   floor item's square" (§6).
9. **`observe_object` is the discovery choke point.** Picking something
   up sets `Item.dknown` — through `rules.apply_discovery`, not by
   assignment, exactly as `rings.py` does. That is what makes
   `xname` say "a scroll labeled FOO" before and "a scroll of
   teleportation" after.
10. **The hazards are named and skipped.** Bag of holding explosions,
    `boh_loss`, the boxed-cat observation, ice boxes, `removed_from_
    icebox` are all §5. They are listed in the module docstring with
    their spans so the next reader knows they were a decision.
11. **`u_handsy` / gloves.** C checks a free hand (wielded weapon,
    shield, cursed gloves). pyhack has `wielded` (PLAN-DROP moves it to
    `W_WEP`) and `is_shield`; the check is three lines and is *in*, so
    "you can't put things in a sack while holding a shield" works from
    the first delivery. The weapons-are-cursed-glued and
    `Gloves_off`-occupation halves are not.

---

## 4. Phases

### Phase A — one at a time, and stacks (~1 session)

*Needs PLAN-INVENT A (model, `addinv`) and B (merging).*

1. `pickup(what=ONE)`: keep the topmost read, but go through
   `invent.addinv` (which merges) instead of the raw append.
2. `pick_obj` / `pickup_object`: the "is it really here / is it the
   chain / is it already carried" checks, `observe_object` via
   `apply_discovery`, and the `count` argument (a split stack).
3. `PickupCommand(all=False)` and `pickup(what=ALL)`: everything on the
   square, in one turn, with the message per item (C emits one line per
   object).
4. Tests: two arrows merge into one letter; `g` twice on a two-item
   square takes them in `items_at` order; `,` takes both in one turn.

**Exit:** the demo floor can be hoovered with `,`; the four existing
`test_pickup.py` tests still pass (they use `pickup(w, "player", rng)`
— keep that signature's default).

### Phase B — capacity (~1.5 sessions)

*Needs PLAN-INVENT D (weight and encumbrance).*

1. `lift_object` and `carry_count` with the gold arithmetic and the
   partial-stack messages.
2. `encumber_msg`: the "You are now burdened" / "no longer burdened"
   pair, comparing `near_capacity` before and after.
3. The 52-letter limit (`invlet_basic`) and the "your knapsack cannot
   accommodate any more items" branch.
4. Tests: a 600-weight loadstone in a 650-capacity pack; a partial
   pickup; the exact message for each of the 5 encumbrance crossings.

**Exit:** pickup can fail; the status line's burden changes at the
right moment; `carry_count` is the only place a partial count is
computed.

### Phase C — containers, the mechanics (~2 sessions)

*Needs PLAN-MKOBJ E (`Item.contents`, `add_to_container`,
`mkbox_cnts`) — this phase is the player-facing half.*

1. `stash_ok` / `u_handsy` / `container_at` / `able_to_loot` /
   `delta_cwt`.
2. `out_container` (put in): `select_many` over the pack, the
   "it won't fit" weight check, `add_to_container`, `weight` recursion,
   the "You put 3 arrows into the chest." line.
3. `in_container` (take out): the same in reverse, plus the
   "there is nothing in it" / "you can't reach into it" cases and the
   `dknown` marking.
4. `use_container`: the t/p/l dispatcher, with `look` reusing
   `simple_look`.
5. Tests: put 20 arrows in, take 5 out, the chest's `owt` follows; a
   contained potion does not show up in `i`; dropping the chest
   (PLAN-DROP) keeps its contents.

**Exit:** a chest from `mkbox_cnts` can be filled, emptied and looked
into; every contained item still satisfies the location invariant.

### Phase D — `#loot` (~1 session)

1. `doloot` / `doloot_core` / `do_loot_cont`: the direction prompt, the
   floor-box case, `able_to_loot`'s refusals ("You cannot reach over
   the chest."), and the in/out choice.
2. `LookInsideCommand` → a `container_id` the core resolves, so the
   "look inside" arm is testable without the console.
3. Tests: looting a box two squares away is refused; looting one you
   are standing on works; looting an empty box says so.

**Exit:** `l` + direction on a floor chest opens the same t/p/l flow as
`l<letter>` on a carried one.

### Phase E — `look_here` (~1 session)

1. `simple_look` / `check_here` / `n_or_more` and the `:` command
   (`invent.dolook`): "You see here a scroll of teleportation." /
   "You see here 3 items." / "You remember where the gold is."
2. The `step._do_move` hook (decision 8) and the audit of the existing
   suite.
3. `describe_decor`'s **subset that exists**: a fountain / sink / altar
   / grave / throne tile under the hero prints C's line only once the
   terrain is generated (PLAN-MKOBJ phase G). Until then the function
   exists and returns nothing for ROOM/CORR.

**Exit:** the `:` command lists the floor pile without picking it up;
walking onto a scroll prints C's line; no existing test changed
semantics.

### Phase F — autopickup (~0.5 session)

1. `World.autopickup: bool` (`True`) and `World.pickup_types: str`
   (`"$"`), `autopick_testobj`, `autopick`.
2. The hook: after a successful move (and after a stair landing).
3. Tests: gold is taken silently; a scroll is not; turning
   `pickup_types` to `"$?!"` takes scrolls and potions too.

**Exit:** with PLAN-MKOBJ's `mkgold` on the floor, walking over gold
adds it to the wallet with the C message, and nothing else is grabbed.

---

## 5. Deliberate divergences

1. **No menu widget.** `query_objlist` / `query_category` /
   `in_or_out_menu` collapse into "the console asks, the core selects":
   `select_many` returns the chosen `(Item, count)` pairs and the
   console supplies the keystrokes. Multi-page menus, `menu_headings`,
   `MENU_TRADITIONAL` etc. are not modelled.
2. **`#tip` is not ported.** Emptying a container is reachable by
   looting it and taking everything (the same outcome, two keystrokes);
   `dotip`'s quiver/tip-through-the-air variants have no analogue.
3. **Bags of holding do not explode, do not lose contents, and are not
   weightless.** `mbag_explodes` / `boh_loss` / `do_boh_explosion` /
   `is_boh_item_gone` / `observe_quantum_cat` / `container_gone` /
   `removed_from_icebox` / `mbag_item_gone` are all unported; a bag of
   holding is an ordinary 0.5-weight container. This is a *gameplay*
   simplification, listed in the module docstring.
4. **No `loot_mon`.** Looting a monster's pack needs `mon.c`'s
   `minvent` and a live monster inventory; monsters hold nothing yet
   (PLAN-MAKEMON phase E gives them gear, but looting them is a later
   wave).
5. **No autopickup exception list.** `check_autopickup_exceptions` is a
   `.nethackrc` feature (`options.c`, 88k tokens, unported).
6. **No `uswallow` gates yet.** `pickup`'s blocked-while-swallowed
   branch is written but unreachable until PLAN-MAKEMON's engulf. It
   stays as a named early return, not a STUB that raises — a swallowed
   hero silently picks nothing up, which is the C behaviour.
7. **Pools and lava are gates, not effects.** "You cannot pick things
   up while swimming" is in; `flooreffects`' "the scroll dissolves in
   the water" is PLAN-DROP's business and needs the water system.
8. **`describe_decor`'s drawbridge/`mention_decor` half is dropped** —
   no drawbridges, no options.

---

## 6. Traps

- **`world.items_at` order is the whole "topmost" story.**
  `items_at` returns dict-insertion order, so `here[-1]` is the most
  recently *placed*. `place_object` (drop) must therefore place items
  such that a re-drop of two items keeps C's pile order, and
  `in_container`'s "take out" must not reorder the floor pile it
  creates. One test asserts `[it.name for it in items_at(pos)]` for a
  three-drop sequence.
- **The `,` (all) loop must iterate over a snapshot.** `pickup(ALL)`
  walks the square while `addinv` may *merge* (removing one of the
  objects) and *delete* (a `useup` inside a refusal path). Iterate
  `list(world.items_at(pos))` and re-check `it.pos == pos` per item.
- **`lift_object` returning "some" is not "none".** The four C
  prefixes (`you cannot … any more` / `it is too heavy for you to …` /
  `you can only … of the …` / `you cannot … any more`) key off
  *whether anything at all* can be lifted and whether the pack is
  empty; getting the branch wrong produces "You cannot lift any more of
  the 20 arrows lying here." when the hero is merely at the limit.
- **The 52-letter limit is not `len(inventory) < 52`.** Gold does not
  take a letter (`COIN_CLASS` is exempt), merged stacks share one, and
  the container pseudo-letters `#`/`-` are outside the range.
  `let_to_name` / `invletter_value` are the authority.
- **`observe_object` must go through `rules.apply_discovery`.** Calling
  `it.dknown = True` directly bypasses the `obj_tables` bookkeeping that
  `xname` reads for the *type*, and the two disagree the moment a
  second scroll of the same type is found.
- **Walking-onto-item messages change the log.** `look_here` in `step`
  is the only change here that can break a pinned test. Audit
  `tests/test_step.py` and `tests/test_console.py` for a path that
  ends on a `worldgen.FLOOR_*` position before turning it on; if one
  exists, either the test asserts the new line (correct) or the phase
  moves after the demo floor kit is rebuilt (PLAN-MKOBJ §3.8).
- **`pickup` must not consume a turn when it fails.** C returns
  `ECMD_OK` for "nothing to pick up" and the world does not tick. The
  demo's habit is that a *failed action* still costs a turn
  (`worn.py` docstring), so decide per path and assert it; a
  `PickupCommand` on an empty square currently still ticks.
- **Containment depth.** A container inside a container is legal in C
  (bags of holding in sacks are not) and `weight` recurses. Guard the
  recursion (depth 1 is enough for this wave) or the first
  `add_to_container` cycle hangs the test suite.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| a pack with a weight and a limit | infinite, weightless |
| arrows / candles / gold that stack in the pack | two lettered "arrow"s |
| containers as a player-facing feature | a chest would be one opaque object |
| `#loot`, put-in, take-out, look-inside | absent |
| "You see here a scroll." / the `:` command | absent |
| autopickup for gold | PLAN-MKOBJ's `mkgold` would be unreachable |
| the shop's "take from the shelf" | PLAN-SPECIAL-ROOMS 4a, blocked on containers + capacity |
| `flooreffects` (what happens when an item lands) | PLAN-DROP; needs `able_to_loot`'s terrain predicates |

| needs | from |
|---|---|
| `quan` / `owt` / `contents` / `carrier` / `invlet` | PLAN-INVENT A (= PLAN-MKOBJ A) |
| `addinv` / `freeinv` / `useup` / `delobj` | PLAN-INVENT A |
| `mergable` / `merged` / `splittable` | PLAN-INVENT B |
| `xname` / `doname` / `an` / `the` / `singular` | PLAN-INVENT C |
| `near_capacity` / `calc_capacity` / `inv_weight` | PLAN-INVENT D |
| `money_cnt` / `findgold` (gold pickup, `carry_count`'s gold arm) | PLAN-INVENT E |
| `select_many` / `loot_classify` / `loot_xname` | PLAN-INVENT G |
| `add_to_container` / `delete_contents` / `mkbox_cnts` / `mkcorpstat` | PLAN-MKOBJ E |
| a real `core/occupation.py` | only for a future multi-turn `#loot`; **not** needed here (§3.5) |
| `minvent` (monster packs) for `loot_mon` | PLAN-MAKEMON E |

---

## 8. Definition of done

- [ ] `pickup(what=ONE|ALL)`; `g` and `,` both work and mean what C
      means
- [ ] `lift_object` / `carry_count` / `encumber_msg` ported with spans;
      pickup can fail, partially and wholly, with C's four messages
- [ ] stacks merge on pickup; `quan` and `owt` agree after every merge
- [ ] `stash_ok` / `u_handsy` / `container_at` / `able_to_loot` /
      `delta_cwt` present
- [ ] `in_container` / `out_container` / `use_container` / `doloot` /
      `do_loot_cont` ported; a chest can be filled, emptied, looked
      into, carried and dropped with its contents
- [ ] `look_here` + the `:` command; the move hook, with the test audit
      done
- [ ] `autopickup` + `pickup_types`, defaulting to gold
- [ ] the location invariant test runs after every pickup/loot test
- [ ] the hazards (BOH, quantum cat, ice box) are documented as
      divergences in the module docstring, with spans
- [ ] `mypy` clean, `flake8` clean, the suite green
- [ ] `ARCHITECTURE.md`'s `pickup.py` line in the module map updated;
      `CHANGES.md` gains the wave
