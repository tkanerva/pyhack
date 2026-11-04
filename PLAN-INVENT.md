# Plan: Wave 6a — the inventory core (`src/invent.c`)

**Status: proposed, nothing implemented.** Written against the tree
that has 521 tests green and mypy clean, with Wave 3 (mklev / mkroom /
mkmap + doors) landed and PLAN-MAKEMON / PLAN-MKOBJ /
PLAN-SPECIAL-ROOMS / PLAN-SPLEV proposed. This is the first of three
documents; they are one wave:

| file | scope | C files |
|---|---|---|
| **this one** | the item model, *where an item is*, letters, stacking, consumption, encumbrance, gold, the naming slice, the display commands | `invent.c`, the encumbrance half of `hack.c`, the naming slice of `objnam.c` |
| PLAN-PICKUP.md | floor → pack, containers, autopickup, `look_here` | `pickup.c` |
| PLAN-DROP.md | pack → floor, pack → hand (wield / quiver / swap / take-off-all) | `do.c` (the drop family), `wield.c` |

**Goal:** `core/invent.py` — the port of `src/invent.c` — so that the
pack becomes a *real* inventory: items that stack, keep their letter,
weigh something, can be consumed one at a time, and can be listed the
way NetHack lists them. Today the pack is a Python list with a
"you pick up the X" message and nothing else.

**Ground truth:** `../NetHack` through `nethack_index`
(`INDEX.md` row `src/invent.c`: 5,731 lines, 55k tokens, 121
functions, pyhack coverage **4%**; `symbols/invent.json` holds the
spans; `PROGRESS.index.md` §10.7 is prose that has drifted — the spans
are the record). Never read `invent.c` whole.

---

## 1. What the C code does (reference)

`invent.c` is not one system; it is five that share a header. Grouped
by what they touch (each name carries its line span):

| group | C functions (`src/invent.c` unless noted) | what it is |
|---|---|---|
| **letters** | `assigninvlet` 693-732 · `invletter_value` 390-399 · `reorder_invent` 738-767 · `compactify` 1626-1660 · `reassign` 4906-4936 · `obj_to_let` 2901-2909 · `let_to_name` 4851-4891 · `display_used_invlets` 3512-3565 | the `a`..`z` `A`..`Z` `#` letter space and its allocation |
| **location** | `addinv_core0` 1055-1148 · `addinv_core1` 959-1005 · `addinv_core2` 1024-1049 · `addinv` 1151-1155 · `addinv_before` 1159-1165 · `addinv_nomerge` 1168-1178 · `freeinv_core` 1355-1399 · `freeinv` 1402-1409 · `delobj` 1429-1433 · `delobj_core` 1437-1462 · `delallobj` 1412-1426 · `useup` 1320-1333 · `useupall` 1311-1317 · `useupf` 4814-4835 · `consume_obj_charge` 1336-1346 · `carry_obj_effects` 1186-1196 · `hold_another_object` 1207-1306 | **the only** code that moves an item between floor / pack / container / gone |
| **stacking** | `merge_choice` 774-810 · `merged` 813-948 · `mergable` 4430-4551 · `stackobj` 4417-4427 · `splittable` 1663-1668 · `check_for_puzzling_nonmerge` 2705-2748 | `quan`, `owt`, BUC / `spe` / erosion / `dknown` merge rules |
| **queries** | `sobj_at` 1465-1475 · `nxtobj` 1478-1491 · `carrying` 1494-1504 · `carrying_stoning_corpse` 1507-1516 · `currency` 1545-1554 · `g_at` 1612-1623 · `obj_here` 1601-1610 · `o_on` 1586-1599 · `u_carried_gloves` 1556-1571 · `is_worn` 2155-2161 · `wearing_armor` 2148-2153 · `is_inuse` 2166-2170 · `taking_off` 1671-1675 · `find_unpaid` 3061-3082 · `count_unpaid` 3571-3584 · `count_buc` 3593-3621 · `tally_BUCX` 3625-3662 · `count_contents` 3665-3697 | the predicates every other system asks |
| **selection** | `getobj` 1751-2089 · `any_obj_ok` 1709-1715 · `getobj_hands_txt` 1718-1736 · `silly_thing` 2093-2131 · `ckvalidcat` 2135-2140 · `ckunpaid` 2142-2146 · `ggetobj` 2201-2369 · `askchain` 2376-2541 · `reroll_menu` 2550-2611 · `mime_action` 1677-1706 | "which item?", the count prefix, the class/category letters, and the refusals |
| **display** | `ddoinv` 3046-3050 · `prinv` 2915-2931 · `xprname` 2935-2995 · `dispinv_with_action` 3004-3043 · `display_pickinv` 3097-3464 · `display_inventory` 3473-3499 · `display_used_invlets` 3512-3565 · `doprgold` 4554-4598 · `doprwep` 4601-4626 · `doprarm` 4652-4690 · `doprring` 4693-4727 · `dopramulet` 4730-4746 · `doprtool` 4766-4787 · `doprinuse` 4791-4809 · `dotypeinv` 3872-4078 · `dounpaid` 3699-3835 · `display_minventory` 5392-5438 · `display_cinventory` 5497-5525 · `display_binventory` 5540-5598 | the `i` list, the per-class lists, the multi-select menus |
| **sorting** | `sortloot_cmp` 402-547 · `sortloot` 592-643 & 654-690 · `unsortloot` 646-651 | five sort modes over a loot array |
| **menus** | `doorganize` 5032-5056 · `adjust_split` 5059-5117 · `doorganize_core` 5119-5338 · `adjust_ok` 4968-4975 · `adjust_gold_ok` 4978-4985 · `check_invent_gold` 4940-4965 · `doperminv` 2854-2898 · `prepare_perminvent` 5600-5614 · `sync_perminvent` 5616-5710 · `perm_invent_toggled` 5712-5729 · `update_inventory` 2822-2851 | `#adjust` and the persistent-inventory window |
| **identification** | `identify` 2645-2651 · `fully_identify_obj` 2631-2642 · `set_cknown_lknown` 2618-2628 · `menu_identify` 2654-2690 · `count_unidentified` 2692-2702 · `identify_pack` 2751-2786 · `learn_unseen_invent` 2790-2816 | the identify scroll's target menu |
| **loot menus** | `loot_classify` 148-305 · `inuse_classify` 69-144 · `loot_xname` 308-387 · `invdisp_nothing` 5341-5357 · `worn_wield_only` 5360-5377 | shared by `pickup.c` and `doupinv` |

Outside `invent.c` but part of the same subject:

| C | span | what | port target |
|---|---|---|---|
| `hack.c weight_cap` | 4295-4349 | `25 × (STR + CON) + 50`, the polyform / levitation / wounded-leg adjustments, `MAX_CARR_CAP` | `invent.weight_cap` |
| `hack.c inv_weight` | 4351-4365 | the pack weight; gold counts `(quan+50)/100` | `invent.inv_weight` |
| `hack.c calc_capacity` / `near_capacity` / `max_capacity` | 4372-4392 | the 0..5 encumbrance level (`UNENCUMBERED` … `OVERLOADED`, `include/hack.h:458`) and the `calc_capacity(xtra_wt)` projection | `invent.calc_capacity` |
| `include/weight.h` | — | `WT_WEIGHTCAP_STRCON = 25`, `WT_WEIGHTCAP_SPARE = 50`, `MAX_CARR_CAP = 1000` | `invent` constants |
| `botl.c enc_stat[]` | 11-13 | `"", "Burdened", "Stressed", "Strained", "Overtaxed", "Overloaded"` — the status line | `invent.ENC_STAT` (read by `ui/console.py`) |
| **objnam.c** naming slice | see §4 phase C | `xname` / `doname` / `an` / `the` / `singular` / `currency` / `ysimple_name` | `core/objnam.py` (**new**) |

Data that already exists in pyhack and is *not* the problem:

- `core/objects.py` — all 480 rows with `weight` (1 cn = 1/100 lb),
  `cost`, `merge` (`oc_merge`), `name_known`, `descr`, `oclass`,
  `material`; `BASES`; the `W_*` masks; `ObjClass`.
- `core/o_init.py` — `ObjTables` with `name_known` / `encountered` /
  `uname` / `descr` / `disco`, and `typename(state, otyp)`: the
  *material* `xname()` is built from.
- `core/hacklib_inflection.py` — `makeplural` / `makesingular` /
  `s_suffix` / `vtense`, i.e. the hard half of `objnam.c` is already
  ported and tested.
- `core/worn.py` — `which_armor` / `setworn` / `is_worn` /
  `wearing_armor`, the worn-mask machinery the display needs
  (`(being worn)` etc.) and the don/doff paths that must now go through
  `freeinv` / `useup`.

---

## 2. Where pyhack stands: two functions out of 121

**Measured:** of `invent.c`'s 121 functions, exactly **two** exist in
pyhack — `wearing_armor` and `is_worn`, both in `core/worn.py`. Every
other mention of the file in the tree is prose (`hunger.py`'s "no
`near_capacity` decrement", `scrolls.py`'s "C: `useup`", …). The
`Item` model is PLAN-MKOBJ's problem; **this** plan is about what the
model is *for*.

### 2.1 `Item` as it is today

```python
Item(id, otype, name, charges, blessed, cursed, pos, container, lev,
     wand_type, potion_type, spell_type, scroll_type,
     otyp, oclass, spe, owornmask, greased, dknown, known, oeaten)
```

Five of the fields the inventory half needs are missing (six counting
the erosion counters, which PLAN-MKOBJ §2 documents as a live
defect), and each one blocks a whole C function group:

| missing | C field | blocks |
|---|---|---|
| `quan: int = 1` | `obj->quan` | `mergable`, `merged`, `useup`, `weight`, every "3 arrows" message, gold |
| `owt: int = 0` | `obj->owt` | `inv_weight` → `near_capacity` → `carry_count` → pickup that can fail |
| `invlet: str = ""` | `obj->invlet` | `assigninvlet`, `obj_to_let`, the `i` list, every `<key><letter>` command |
| `contents: List[str]` | `obj->cobj` | containers (PLAN-PICKUP); and "carrying a container" is a weight that is not `oc_weight × quan` |
| `carrier: Optional[str]` | `obj->where == OBJ_INVENT/MINVENT` + `ocarry` | the rename; **`Item.container` means the carrier today** (PLAN-MKOBJ §2) |
| `oeroded` / `oeroded2` | same | `mergable` reads them; PLAN-MKOBJ §2 has the live `erode_obj` defect |

**These are the same fields as PLAN-MKOBJ phase A, and phase A of this
plan is the same work.** Do it once, in one commit, listed in both
plans' phase A. This document does not repeat the model table; it
takes the post-phase-A model as given.

### 2.2 Live defects this plan fixes

1. **The letter drift.** `ui/console.py:_item_by_letter` maps `a` +
   *index into `hero.inventory`*. Pick up an apple and nothing moves;
   drop the chain mail and **every later item is re-lettered** — the
   letter the player learned for the cloak is now the gloves'. C has no
   such failure mode: `assigninvlet` gives an item a letter once and
   `flags.invlet_constant` (default on) keeps it. This is invisible in
   the current 6-item demo and becomes the first thing a real pack
   does. Not covered by any test.
2. **Four writers of "where is this item".** `core/items.consume_item`
   (pops `world.items` + filters `inventory`), `core/worn.
   _remove_destroyed` (same, inline), `core/pickup.pickup` (sets `pos` /
   `container` / appends), and `conftest.make_world` (appends from the
   `container` field). They already disagree: only
   `_remove_destroyed` clears the worn mask, and neither clears
   `Monster.wielded`. Every function in the **location** group in §1 is
   a caller that must go through one of the five instead.
3. **`consume_item` will orphan container contents.** It deletes the
   item from `world.items` unconditionally. With containers
   (`Item.contents`) landing in PLAN-PICKUP, eating the last item of a
   stack, or destroying a chest, leaves the contents as `Item`s with
   `pos is None` and `carrier is None`: unreachable by `items_at`,
   unrenderable, unpoppable — a permanent leak inside `world.items`.
   C's `useup` decrements `quan` and only calls `useupall` (→
   `freeinv` → `obfree`, which *deletes contents too*) at zero.
4. **Nothing can fail.** `pickup` has no capacity check, so the pack is
   unbounded and `Item.owt` has no reader. `hunger.py:287` already
   documents the consequence: "C: `near_capacity() > SLT_ENCUMBER` —
   no encumbrance".

---

## 3. Design decisions

1. **`core/invent.py` is the single writer of item location** — the
   `rules.apply_damage` pattern applied to items. Five entry points:
   `addinv` (→ pack), `freeinv` (pack → loose), `useup` / `useupall`
   (pack → gone, one at a time), `delobj` (anywhere → gone), and
   `place_object` (loose → floor). Nothing else may set
   `Item.pos` / `Item.carrier` / `Item.contents`, append to or filter a
   `Monster.inventory`, or `pop` from `World.items`. `items.consume_item`
   is deleted (its 12 call sites become `invent.useup`); `worn.
   _remove_destroyed` becomes `invent.delobj`; `pickup.pickup` calls
   `invent.addinv`; `conftest.make_world` keeps its one-line append but
   gains a test asserting the invariant (see §6).
2. **The inventory list is kept ordered by invlet, not by insertion.**
   Merging must not move an item, and `obj_to_let` has to be O(1) for
   the display. `addinv` inserts at the letter's position (or appends
   with the next letter); a test asserts `[it.invlet for it in
   inv] == sorted(...)` after every mutating operation.
3. **Letters are allocated C's way**: `assigninvlet` walks
   `invletter_value`'s order (`a-z`, `A-Z`, then `'#'` for the
   overflow/"many" bucket and the container pseudo-letters `CONTAINED_SYM`
   / `HANDS_SYM`), skipping letters `let_to_name` says are in use, with
   `flags.invlet_constant` on (the default) so a letter is never
   reused while it is held. `reorder_invent` and `compactify` exist as
   named arms but are only reached by `#adjust` / a full pack, which
   this wave does not expose.
4. **Merging is `mergable(obj, otmp) -> bool` + `merged` as one
   function pair, ported whole.** The predicate is 120 lines of C for a
   reason: same `otyp` and `oc_merge`; always for coins; equal
   `blessed` / `cursed`; equal `spe`, `oeroded`, `oeroded2`,
   `oeaten`, `olocked`, `otrapped`, `lamplit`, `unpaid`, `no_charge`;
   equal `dknown`, and `bknown` unless the hero is a Cleric and not
   Blind/Hallucinating. The `how_lost` / `bypass` / glob halves are
   dropped with the throwing and glob work (§5.3).
5. **`owt` is computed by `weight(item)` on every write, never edited.**
   `weight` is PLAN-MKOBJ §3.5; this plan only *reads* it (in
   `inv_weight`). The one rule worth repeating here: `oc_weight` is in
   1/100 lb and gold is `(quan + 50) / 100` — the "currency weight"
   special case of `inv_weight`, mirrored in pickup's `GOLD_WT`.
6. **Encumbrance is computed, never cached** — the `worn.uac` style.
   `weight_cap(mon)` uses `rules.current_ability(mon, "str"/"con")` (so
   a worn ring of gain strength matters for free), `inv_weight(mon)`
   sums the pack, `calc_capacity(mon, xtra_wt)` returns 0..5. There is
   no `Monster.encumbrance` field, and no invalidation to forget.
   `ui/console.py` prints `ENC_STAT[near_capacity(hero)]` on the status
   line the way `botl.c` does.
7. **`getobj` is split in two: the UI resolves the key, the core
   validates the choice.** pyhack's `Command` carries an `item_id`, so
   C's interactive loop (1751-2089) is the *console's* job; but every
   refusal in it — "You don't have that object.", "You don't have that
   many! You have only 3.", `silly_thing`'s "Use the 'W' command to
   wear armor.", `ckvalidcat`'s "That is a silly thing to …" — is
   game logic and must live in the core where a test can assert it.
   `invent.select(world, mon, item_id, word, count=0, **filters) ->
   (Item, int) | List[Event]` is that function. The console keeps a
   *pure* `letter → item_id` lookup and the count prefix parse.
8. **`Item.name` stays as the demo's hand-written string, and
   `objnam.xname()` returns it when `otyp == 0`.** Every demo item
   (`worldgen.FLOOR_*`, the starting kit) has `otyp == 0` and a
   perfectly good `name`; every `mksobj` item has a real `otyp` and a
   name that must be *computed* (BUC prefix, `+N`, erosion word, `(being
   worn)`, quantity, "of <monster>" for a corpse). Two paths, one
   function, no test churn — the same bargain PLAN-MKOBJ §3.8 strikes
   for the demo floor kit. `Item.name` on a `mksobj` item becomes
   `None` and is never read.
9. **The naming slice is 15 functions, not 89.** `objnam.c` is 5,734
   lines and most of it is hallucination, `xcalled`, fruit names,
   `oname`, and the shop's `paydoname`. The inventory needs
   `obj_typename`, `xname_flags` (the long one), `doname`, `singular`,
   `an` / `An` / `the` / `The` / `just_an`, `aobjnam` / `yobjnam` /
   `Tobjnam`, `ysimple_name` / `Ysimple_name2`, `simple_typename`,
   `add_erosion_words`, `erosion_matters`, `currency`,
   `doname_vague_quan`. Everything else stays unported and is named in
   the module docstring.
10. **`sortloot` is a pure key function.** `sortloot(items, mode) ->
    List[Item]` returns a new list; `SORTLOOT_INVLET` (the default) is
    the sorted-by-letter order, `SORTLOOT_LOOT` the class/`otyp`/
    BUC order the menus use. No stored order, no `unsortloot`.
11. **`unpaid` items are PLAN-SPECIAL-ROOMS' business, and this plan
    only leaves the holes.** `mergable` tests `unpaid` and `no_charge`
    (both `False` until shops land); `consume_obj_charge(obj,
    maybe_unpaid)` takes the flag and ignores it;
    `invent.costly_alteration` is a no-op hook. The moment shk.c ports
    those two fields become live and nothing in this module changes.
12. **`Item.charges` is retired in favour of `spe`.** Same call as
    PLAN-MKOBJ §2: `consume_obj_charge` decrements `spe`; `zap.py` /
    `spells.py` / `scrolls.py`'s dozen `charges` reads migrate in the
    phase-A commit and the field is deleted.
13. **`#adjust`, the persistent-inventory window, and `doperminv` are
    out of scope** (§5.6) — they are a UI feature with no gameplay
    content, and the console has no window.

---

## 4. Phases

### Phase A — the model and the one writer (~1.5 sessions)

The same commit as PLAN-MKOBJ phase A, done once:

1. `Item` gains `quan`, `owt`, `invlet`, `contents`, `oeroded`,
   `oeroded2`, `olocked`, `otrapped`, `corpsenm`; `container` is
   renamed `carrier`; `charges` becomes `spe`.
2. `core/invent.py` with the location functions and *no* callers moved
   yet: `addinv`, `freeinv`, `useup`, `useupall`, `delobj`,
   `place_object`, plus id plumbing (ids come from `World.new_ident`,
   PLAN-MAKEMON §3).
3. Move the existing call sites: `items.consume_item` deleted (12
   uses → `useup`), `worn._remove_destroyed` → `delobj`,
   `pickup.pickup` → `addinv`, `worldgen` → `addinv`. **Leave
   `Monster.wielded` alone**: `scrolls.py:142`'s hand-written
   `mon.wielded = None` stays until PLAN-DROP phase C deletes the field
   and replaces it with `wield.setuwep(None)` — otherwise these two
   plans would each need the other first.
4. `assigninvlet` / `obj_to_let` / `let_to_name`; `_item_by_letter`
   becomes a letter lookup, not an index.
5. Invariant test: for every `Item` in `world.items`, exactly one of
   (`pos`, `carrier`, a parent's `contents`) holds, and every
   `carrier`/`contents` id resolves. Run it from a `conftest` helper
   the other suites can call after their own mutations.

**Exit:** all 521 existing tests pass with only mechanical edits; the
letter-drift test (drop the second item, assert the third keeps its
letter) passes; deletion of a *container* deletes its contents.

### Phase B — stacking (~1 session)

1. `mergable` + `merge_choice` + `merged`, whole, minus §5.3's drops.
2. `quan` in the messages: `pickup` says "You pick up 3 arrows.";
   `_inventory_line` shows "3 arrows".
3. `splittable` (a count prefix on a stack) — used by pickup and drop.
4. Tests: a cursed and a blessed arrow do not merge; two `spe`-different
   daggers do not merge; gold always merges; merging upstreams an
   `owt` recompute; `merged` returns the survivor.

**Exit:** `merged` is the only writer of `quan` except `mksobj`, and a
10k-draw property test finds no pair that merges and then fails the
`quan == sum` invariant.

### Phase C — naming (`core/objnam.py`) (~2 sessions)

This is the phase that makes every other message correct: pickup,
drop, eat, read, "your X glows", the inventory list.

1. `obj_typename` / `simple_typename` (`o_init.typename` is the body;
   `objnam` adds the "strange object" and unknown-class cases).
2. `xname_flags`: the class switch (`"ring of X"`, `"potion of X"`,
   `"scroll labeled X"` when `descr` is unknown, `"corpse of X"`,
   `"<N> arrows"`), the BUC prefix, `"uncursed"` only when `known`,
   `+N`/`-N` where `spe` is visible, `add_erosion_words`, and the
   worn/wielded suffix (`(being worn)`, `(on left hand)`,
   `(wielded in right claw)` → `(wielded)`).
3. `doname` (xname + quantity + `an`/`the`), `singular`, `an`/`An`/
   `the`/`The`/`just_an` (the vowel test C uses, not `in "aeiou"`),
   `aobjnam`/`yobjnam`/`yobjnam2`/`Tobjnam` (the verb agreement the
   erosion code wants), `ysimple_name`/`Ysimple_name2`,
   `doname_vague_quan` ("some" for a big stack), `currency`
   ("zorkmid"/"zorkmids").
4. Route the existing messages through it: `pickup`, `hunger`,
   `scrolls`, `worn._on_msg`, `ui/console._inventory_line`,
   `zap`. Demo items keep `Item.name` (decision 8), so the pinned
   message tests stay pinned.

**Exit:** a table test over 30 `otyp`s × (BUC × `spe` × erosion ×
`quan`) renders exactly the C strings; the existing exact-message tests
pass unchanged; `mypy` clean.

### Phase D — weight and encumbrance (~1 session)

1. `weight_cap` / `max_capacity` / `inv_weight` / `calc_capacity` /
   `near_capacity`, `ENC_STAT`, the `WT_*` constants.
2. Status line: `Burdened` … `Overloaded` appended (the `botl.c` slot
   the AC/hunger already use).
3. Turn on the two documented simplifications that were waiting for
   this: `hunger.py:287`'s "food is less filling when burdened", and
   `mhitu`/`trap`'s `near_capacity() > SLT_ENCUMBER` "you cannot carry
   that" paths (each gated on a `# TODO` that names this plan).
4. `carrying` / `carrying_stoning_corpse` / `o_on` / `g_at` /
   `obj_here` / `is_inuse` / `sobj_at` / `nxtobj` — the small
   predicates, tested directly.

**Exit:** `near_capacity` is 0 for the starting kit and 1..5 as the
floor is hoovered; `pickup` in PLAN-PICKUP phase B can now fail.

### Phase E — gold (~1 session)

1. `money_cnt` / `findgold` / `hidden_gold` (`invent.c`'s `g_at` plus
   the container walk), `doprgold` ("Your wallet contains N zorkmids.").
   *Note:* PLAN-MKOBJ phase D plans the same read under the name
   `hero_gold(world)` — it is the same function; whichever phase lands
   first owns it and the other drops its copy. The C name wins.
2. `mkgold` merging into a carried pile (the `GOLD_WT` arithmetic in
   `carry_count`, pickup.c 60-62 — shared constant).
3. Wire `uhitm.steal_it`'s leprechaun-gold STUB and the
   gold-detection scroll STUB (both are one-liners once `money_cnt`
   exists).

**Exit:** the hero can carry gold, drop it (PLAN-DROP), pick it up
(PLAN-PICKUP) and be robbed; the pile merges on every re-`mkgold`.

### Phase F — the display half (~2 sessions)

1. `xprname`, `prinv`: `<-letter-> name (N in total)` in the exact C
   column layout.
2. `format_inventory(world, mon) -> List[str]` (`display_inventory` +
   `display_pickinv`'s non-menu path), `dotypeinv` per class
   (`) [` `" = (`), `doprwep` / `doprarm` / `doprring` / `dopramulet` /
   `doprtool` / `doprinuse` / `doprgold`.
3. Console: `i` prints the list, `)` `[` `"` `=` `(` print a class.
   These are *renders*, not commands: they consume no turn (C:
   `ECMD_OK`), so they are a new `ListCommand(what)` the UI answers
   itself from `world` — the core exposes only the formatter. Add one
   small test asserting `ECMD_OK`-ness by construction (the formatter
   mutates nothing: deep-compare the world before/after).
4. `count_buc` / `tally_BUCX` / `count_contents` (the menu tallies).

**Exit:** `i` on the starting kit prints five lines with `a`..`e`,
`*` marks on the worn ones, and the chain mail's `(being worn)`; the
gold/class lists work; rendering allocates no state.

### Phase G — selection and menus (~1.5 sessions)

1. `invent.select` (decision 7): the filter vocabulary (`any_obj_ok`,
   `ckvalidcat`, `ckunpaid`, `allow_category`, `is_worn_by_type`,
   `this_type_only`), the count prefix (`splittable` / `adjust_split`),
   and `silly_thing`'s refusal table.
2. `ggetobj` / `askchain`: the multi-item loop, expressed as
   `select_many(world, mon, word, **filters) -> List[Tuple[Item, int]]`
   — the *pure* half of "drop several things", consumed by
   PLAN-DROP phase B.
3. `loot_classify` / `inuse_classify` / `loot_xname`: the classification
   that both the drop menu and the loot menu use.

**Exit:** every refusal message C has is reachable from a unit test;
`select_many` is the only selection helper the drop/wield/loot code
needs.

### Phase H — deferred, listed so nobody re-decides

`doorganize` / `doorganize_core` (`#adjust`), `doperminv` /
`prepare_perminvent` / `sync_perminvent` (persistent inventory
window), `identify*` (the identify scroll's target menu — lands with
the identification port), `dounpaid` / `find_unpaid` / `count_unpaid`
(PLAN-SPECIAL-ROOMS), `reroll_menu`, `mime_action`.

---

## 5. Deliberate divergences

1. **No linked list.** `world.items` is a dict keyed by id; the pack is
   a `List[Item]` ordered by invlet. C's `nobj` / `nexthere` chains are
   replaced by (a) the list order and (b) `items_at()`'s insertion
   order for the floor pile. Consequence: "topmost" is the last placed
   (`pickup.pickup` already documents this).
2. **No `struct obj *` identity games.** `merged(&otmp, &obj)`'s
   pointer swapping becomes "return the survivor `Item`"; C's
   `obj_extract_self` disappears because the five location functions
   are the only mutators.
3. **`how_lost`, `bypass`, globbing, `nomerge`** are dropped with the
   throwing system; `mergable` keeps the whole *observable* rule set.
4. **No inventory-window events.** C's `update_inventory()` marks the
   window dirty; here the UI redraws every turn, and
   `invent.update_inventory` exists only as a no-op name for the C
   call sites to hang off.
5. **`invlet_constant` is not a flag.** The C option can be turned off;
   here the constant-letter behaviour is unconditional (the option
   belongs to `options.c`, which is unported).
6. **`#adjust` does not exist.** No reordering command, no
   `flags.sortpack`; letters are assigned in the order items are
   acquired.
7. **Encumbrance has no movement cost yet.** `near_capacity >= HVY`
   slows movement and forbids diagonal squeezes in C (`hack.c:3057`);
   `step.py`'s movement is one tile per command, so the level only
   feeds the status line and the pickup/`carrying` refusals until the
   movement rework.
8. **`sortloot`'s `SORTLOOT_PACK` / `SORTLOOT_LOOT` modes are one
   key function each**, not the 146-line `qsort` comparator with its
   tie-breaking by `invlet_value`; ties break by letter, which is what
   the comparator does at the end anyway.

---

## 6. Traps

- **The rename is load-bearing.** `Item.container` means *carrier*
  today: 15 sites in `core/` + `ui/`, 22 in `tests/`, 1 in
  `conftest.py` (PLAN-MKOBJ §6 measured 13 when it was written; the
  later waves' tests have added the rest). If
  `contents` is added without renaming, `add_to_container` sets
  `container=<id>` and `worn.which_armor` / `pickup` / `world.items_at`
  silently start treating a contained item as carried. Rename first,
  grep for `.container`, and make `make_world`'s `if it.container`
  become `if it.carrier`.
- **The letter change touches the UI contract.** `ui/console.py`'s
  `_item_by_letter` and `main.py`'s printed help both describe the
  index scheme ("the letters are the inventory letters shown on the
  screen"). PLAN-DROP changes the *key bindings* in the same wave;
  do the letter work here and the keymap work there, and update
  `main.py`'s help text in both commits.
- **`useup` vs `useupall` vs `delobj` are not interchangeable.**
  `useup` decrements `quan` and stops at 1 (`useupall` only at
  `quan == 1`); `delobj` deletes *and* deletes contents. Getting this
  wrong once means a wand of striking with 0 charges that stays in the
  pack forever, or a chest whose contents become ghosts. The three get
  separate tests with the same fixture.
- **`merged` must not merge across `charges`.** After the `spe`
  migration, a `spe=3` wand and a `spe=7` wand of the same type must
  not stack — that is what makes recharge bookkeeping survive.
- **`weight` units.** `oc_weight` is 1/100 lb and `WC` in C is
  centigrams; `inv_weight` compares against `weight_cap`, which is
  `25 × (STR+CON) + 50` in the same unit. A "fix" to grams silently
  makes the hero able to carry 100× NetHack's load.
- **The pinned demo kit.** `test_same_seed_same_game`, `test_demo.py`
  and `test_pickup.py` pin item *names* and *positions*. Decision 8
  (the `otyp == 0` name fallback) exists to keep them pinned; a phase
  that "improves" a demo item's name by giving it an `otyp` breaks
  three suites at once.
- **`ObjTables` rng.** `o_init` shuffles descriptions on its own rng
  stream on purpose (PLAN-MKOBJ §6). `xname` must never draw — it is a
  pure function of the item plus `world.obj_tables`.
- **`select` must not consume a turn on refusal.** C returns
  `ECMD_OK`/`ECMD_FAIL` and the command is free; the demo's habit is
  "a failed command still costs a turn" (`worn.py`'s docstring). Keep
  the demo habit for *actions*, but a plain `i` listing and a
  `silly_thing` refusal must not tick the world — assert it.

---

## 7. What this unblocks / what blocks it

| unblocked | was |
|---|---|
| `pickup` that can fail (capacity) | always succeeds |
| stacks: arrows, candles, gold piles, "3 in total" | one `Item` per object, `quan` absent |
| containers as a weight and a location | `Item.contents` absent |
| the `i` / `)` / `[` / `"` / `=` / `(` commands | only the one-line `🎒` summary |
| encumbrance on the status line; the `hunger.py` burdened-food rule | "no `near_capacity` decrement" |
| PLAN-PICKUP.md (all of it) | blocked on `addinv`/`owt`/`mergable` |
| PLAN-DROP.md (all of it) | blocked on `freeinv`/`useup`/letters |
| PLAN-SPECIAL-ROOMS' bill | needs `unpaid` + `money_cnt` |
| the identify scroll's target menu | needs `select` |

| needs | from |
|---|---|
| `quan` / `owt` / `contents` / `carrier` / `oeroded` / `invlet` fields | PLAN-MKOBJ phase A (same commit) |
| `weight(item)` | PLAN-MKOBJ §3.5 |
| `World.new_ident` | PLAN-MAKEMON §3 (same commit as PLAN-MKOBJ A) |
| `mksobj`-made items to display | PLAN-MKOBJ B–D; the *display* works on hand-made items today |
| `unpaid` / `no_charge` / `costly_alteration` | PLAN-SPECIAL-ROOMS phase 4b |
| the identification system (`bknown`, `rknown`, `cknown`) | a future identification plan; `xname` takes them as "always known" for now |
| `core/occupation.py` (the real one) | for multi-turn `#loot`/`#tip` only — see PLAN-PICKUP §5 |

---

## 8. Definition of done

- [ ] `core/invent.py` exists and is the **only** writer of
      `Item.pos` / `carrier` / `contents` / `Monster.inventory` /
      `world.items`
- [ ] `items.consume_item` is deleted; `worn._remove_destroyed` is a
      call to `invent.delobj`
- [ ] `Item` has `quan` / `owt` / `invlet` / `contents` / `carrier` /
      `oeroded*`; `charges` is gone
- [ ] the invariant test (exactly one location per item; every id
      resolves) runs in every suite that touches items
- [ ] the letter-drift test passes; `_item_by_letter` is a lookup
- [ ] `mergable` / `merged` / `merge_choice` ported with spans in the
      docstrings; cursed+blessed and `spe`-different items never stack
- [ ] `core/objnam.py` renders `xname` / `doname` / `an` / `the` /
      `singular` / `currency`; the demo items keep their stored names
- [ ] `weight_cap` / `inv_weight` / `near_capacity` / `ENC_STAT`; the
      status line shows the burden; two documented "no encumbrance"
      simplifications are closed
- [ ] `money_cnt` / `findgold` / `doprgold`; the leprechaun and gold
      detection STUBs are filled
- [ ] `i` and the per-class lists render from `xprname`
- [ ] `invent.select` / `select_many` give every C refusal message a
      test
- [ ] `mypy` clean, `flake8` clean, existing 521 tests green
- [ ] `ARCHITECTURE.md` gains the invent row in the module map and the
      "single writer" paragraph; `CHANGES.md` gains the wave
