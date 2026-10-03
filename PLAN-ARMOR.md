# Plan: defence system with armours

**Status (2026-10-01):** Phases 1 and 2 are implemented and tested
(`core/worn.py`, `core/pickup.py`, the `mhitu` AC integration, the three
commands, the console keys and the demo gear).  Corrections made while
executing, against this plan's arithmetic: (a) the plan's "plate 3" in
the Phase-1 `arm_bonus` list is the macro's ac argument -- the actual
`ARM_BONUS(plate mail)` is **7** (`a_ac = 10 - 3`); (b) the plan's
"chain 5 + cloak 1 + helmet 1 + shield 1 + gloves 1 + boots 1 = effective
1" is **0** (10 - 10); (c) the "goblin -> threshold 17" mhitu test case
matches the hill orc (mlevel 2), not the goblin (mlevel 0, threshold
15).  Phase 3 (magic_negation / u_slip_free) and Phase 4 (erosion) are
the next series; Phase 5 stays out of scope.

Goal: the hero's defence stops being a fixed `Monster.ac` constant and becomes
a NetHack defence system: the hero wears armour in the seven C slots
(suit / cloak / shirt / helmet / shield / gloves / boots), plus rings and an
amulet; the effective AC is computed from the worn gear (C `find_ac()`);
monster attacks use the C hit differential and the negative-AC damage
reduction; the hero can pick up, wear and take off gear.

Ground truth is the NetHack 5.0 C source (local clone at `../NetHack`).
Everything below is written to the established porting conventions: pure
functions over `World`, events out, STUBs that raise `NotImplementedError`
for unported machinery, table-driven deterministic tests with `SeqRng`.

---

## 1. What the C code actually does (reference)

| Mechanic | C location | Notes |
|---|---|---|
| Worn-slot masks `W_ARM` `W_ARMC` `W_ARMH` `W_ARMS` `W_ARMG` `W_ARMF` `W_ARMU` `W_AMUL` `W_RINGL` `W_RINGR` `W_TOOL` | `include/prop.h` | `W_ARMOR`, `W_ACCESSORY`, `W_WEP`, ... aggregates |
| Slot accessors | `src/worn.c` `which_armor()` (scans inventory for `owornmask & flag`); `src/invent.c` `wearing_armor()`, `is_worn()`; `src/worn.c` `setworn()` | The hero uses globals (`uarm`, ...), monsters scan `minvent` — same mask mechanism |
| Per-item armour data | `include/objclass.h`: `a_ac` == `oc1`, `a_can` == `oc2`; `include/obj.h`: `oc_armcat` (`ARM_SUIT`..`ARM_SHIRT`), `oc_delay`, `is_suit/is_cloak/is_shield/is_helmet/is_gloves/is_boots/is_shirt` macros | Already in `core/objects.py`: `Object.oc1` (built as `10 - ac`, i.e. `a_ac`), `oc2` (`a_can`), `subtyp` (`oc_armcat`), `delay` (`oc_delay`), `oprop` |
| AC bonus of one item | `include/hack.h` `ARM_BONUS(obj)` = `objects[otyp].a_ac + obj->spe - min(greatest_erosion(obj), a_ac)` | `greatest_erosion` already ported in `core/weapon.py` (getattr with 0 default) |
| Effective AC | `src/do_wear.c` `find_ac()`: `mons[u.umonnum].ac` (base) − Σ `ARM_BONUS` over the 7 slots − `spe` of worn protection rings (left+right) − 2 for amulet of guarding − `u.ublessed` (intrinsic Protection) − `u.uspellprot`, clamped to ±`AC_MAX` (99, `you.h`) | Base AC for a human is **10** (`monsters.h`: `MON(NAM("human"), S_HUMAN, LVL(0, 12, 10, 0, 0), ...)`); the human row is NOT in `core/monst.py`'s `SUBSET_PM`, so the hero's base is a named constant |
| Hit differential | `src/mhitu.c` `mattacku()`: `tmp = AC_VALUE(u.uac) + 10 + m_lev`; `AC_VALUE(AC)` = `AC >= 0 ? AC : -rnd(-(AC))` (`include/hack.h`) — a negative AC rolls, so it is strictly better than 0 but never fully immune | `core/mhitu.py` currently uses `hero.ac + 10 + level` (raw, no `AC_VALUE`); fine while AC ≥ 0, must change once gear can push AC negative |
| Negative-AC damage reduction | `src/mhitu.c` `hitmu()`: if `u.uac < 0` and damage > 0: `dmg -= rnd(-u.uac)`, min 1 | `core/mhitu.py` already implements this against `hero.ac` — needs to switch to the computed AC |
| Donning | `src/do_wear.c` `dowear()`/`doputon()` → `accessory_or_armor_on()` (validates via `canwearobj()`, `setworn()`, per-type `<Type>_on()` side effects, `oc_delay` occupation); messages "You are now wearing ..." / prinv for rings & amulets | Per-type side effects are all intrinsic-property work (stealth, speed, Protection, ...) — out of scope here |
| Doffing | `dotakeoff()`/`doremring()` → `armor_or_accessory_off()` → `select_off()` (cursed → "You can't. It is cursed."; suit/cloak/shirt layering; gloves-vs-welded-weapon; boot traps) then `<Type>_off()`; message "You were wearing ..." | `cursed()` in C also covers welded weapons; the demo has no welding (wield.c unported) |
| Magic defence | `src/mhitu.c` `magic_negation()`: `mc` = max `a_can` of worn armour; +2 if amulet of guarding confers Protection, +1 if any other Protection source; capped 3; used by `defended()` in zap/spell defence | `core/mhitu.py` has the STUB; no live call site until monster spellcasting / zaps-on-hero are ported |
| Slippery gear | `src/mhitu.c` `u_slip_free()`: greased cloak/suit/shirt (or oilskin cloak) sheds AT_HUGS/AT_TENT+AD_WRAP attacks; cursed gear fails 1/3; grease wears off 1/2 | STUB in `core/mhitu.py`; no demo monster hugs yet |
| Erosion / destruction | `src/trap.c` `erode_obj()` (burn/rust/rot/corrode/crack; enchantment + `oeroded` counters; destroys at max), `src/objnam.c` `erosion_matters()`, `src/do_wear.c` `obj_erode_type()`, `disintegrate_arm()` (destroy-armor scroll), `destroy_arm()` | Phase 4 |

Already in pyhack that the plan builds on:

- `core/objects.py`: complete `OBJECTS` table with `a_ac` (`oc1`), `a_can`
  (`oc2`), `oc_armcat` (`subtyp`), `oc_delay`, `oc_oprop`, `Material`,
  `Prop`, the `ARM_*` category constants.
- `core/weapon.py`: `greatest_erosion()`, `ObjLike` protocol,
  `bimanual()` (needed for the shield/two-handed check).
- `core/types.py` `Item`: `spe`, `blessed`, `cursed`, `oclass`, `otyp` —
  missing only the worn state (below).
- `core/mhitu.py`: the mattacku loop, hitmu/missmu, the negative-AC
  reduction (currently against `hero.ac`).
- `core/items.py`: `wielded_of()` (the shield-vs-two-handed check reads the
  wielded item through it).

---

## 2. Design decisions (decide once, keep consistent)

1. **Worn state = `Item.owornmask` (a `prop.h` bitmask) + inventory scan.**
   Add `owornmask: int = 0` to `Item`. No per-slot fields on `Monster`:
   `which_armor(world, mon, mask)` scans `mon.inventory` for
   `owornmask & mask` — the exact C mechanism monsters already use, applied
   uniformly to hero and (future) monsters. One mechanism, no hero special
   case.
2. **`Monster.ac` becomes the BASE (body) AC; effective AC is computed, not
   cached.** `worn.uac(world, mon)` = `mon.ac − ac_bonus(...) − spellprot
   − ublessed`, clamped to ±99 (the `find_ac()` computation minus the
   `AC_VALUE` randomisation). No cache to invalidate: gear changes and the
   next query agree by construction.
   - Demo hero: `worldgen` sets `hero.ac = 10` (C `mons[PM_HUMAN].ac`; the
     human row is not in the monst.py subset, so a named constant
     `HERO_BASE_AC = 10` with a comment) and starts wearing **chain mail**
     (`a_ac = 5`) → effective AC **5, exactly the demo's current defence**.
     Seed-42 game balance is unchanged.
   - `conftest.make_hero` keeps `ac=5` and no gear → effective 5 → **every
     existing test's hit differential and RNG draw order is unchanged**
     (see determinism note below).
3. **C-faithful combat integration:** the mattacku differential uses
   `AC_VALUE` (rolls only when effective AC < 0) and hitmu's damage
   reduction uses the computed AC.
4. **Donning/doffing consumes one turn each.** C uses `oc_delay`
   occupations (`nomul`, `set_occupation`); pyhack has no occupation system.
   Documented simplification; the `oc_delay` data stays in the table for
   the later port. Failed commands also consume a turn (consistent with
   today's quaff/cast behaviour).
5. **One command pair, like C's shared code path:** C's `W`/`P` (wear/puton)
   both funnel into `accessory_or_armor_on()` and `T`/`R` (takeoff/remove)
   into `armor_or_accessory_off()`. So pyhack gets
   `WearCommand(item_id)` (armor + rings + amulet) and
   `TakeOffCommand(item_id)` (same), not four commands.
6. **No identification.** Demo items are fully known (names, `+N`
   enchantment visible). C's "wearing reveals the enchantment via the AC
   change" (`known`, `bknown`, `set_bknown`) is deferred with the
   identification system — noted as a simplification, not faked.
7. **No intrinsics.** Worn-gear properties (stealth boots, cloak of
   protection, fire-resistant dragon mail, ...) need the `u.uprops[]`
   extrinsic/blocked/intrinsic property system (prop.h masks over
   `Object.oprop`). The AC computation already anticipates it:
   `uac()` takes `ublessed`/`spellprot` as zero until the priest/spell
   ports land. All `<Type>_on()`/`<Type>_off()` side effects are STUBs.
8. **Wielding stays on `Monster.wielded`.** Migrating the wielded weapon to
   `owornmask`'s `W_WEP` bit is a cross-cutting refactor (items.py,
   worldgen, tests) with no defence benefit — deferred, noted.
9. **Monster armour is out of scope.** Monsters don't carry items in the
   runtime yet (the mon.c port brings `minvent`). `uac()` is written
   generically over `Monster` so that port reuses it; `uhitm.known_hitum`
   keeps reading the monster's `PerMonst.ac`.
10. **Floor gear + a pickup subset.** The demo floor is currently item-free
    and there is no pickup. Add a handful of armour items at **fixed
    positions reserved via `generate_map(keep_floor=...)`** (no RNG draws →
    the seed-42 layout, trap/monster placement and every seeded test are
    untouched) and a `core/pickup.py` subset (C `pickup.c` `pickobj()`):
    take the topmost item on the hero's tile, "You pick up the X.", no
    merging, no inventory cap (C `INV_MAX` deferred, noted).

Determinism note (important): with effective AC ≥ 0, `AC_VALUE` makes **no
RNG draw**, so the only new draw in the whole defence feature appears when
the hero reaches negative AC (full gear + rings) — exactly when the new
behaviour is being exercised. Existing seeded tests are byte-for-byte
unaffected.

---

## 3. Phases

### Phase 1 — worn data model + AC core (the heart)

New module `core/worn.py` (port of the AC half of `do_wear.c` + the
slot half of `worn.c`/`invent.c`). Docstring in the house style: C
provenance, what's included, STUBs, simplifications.

Tasks:

1. `core/objects.py`: port the `prop.h` worn masks — `W_ARM`, `W_ARMC`,
   `W_ARMH`, `W_ARMS`, `W_ARMG`, `W_ARMF`, `W_ARMU`, `W_ARMOR`, `W_AMUL`,
   `W_RINGL`, `W_RINGR`, `W_RING`, `W_TOOL`, `W_ACCESSORY`, `W_WEP`,
   `W_SWAPWEP`, `W_QUIVER`, `W_WEAPONS` — next to `Prop`.
2. `core/types.py` `Item`: add `owornmask: int = 0`. Update the `Monster.ac`
   docstring: base (body) AC; effective AC via `core.worn.uac`.
3. `core/worn.py` (new), pure functions:
   - predicates (C `obj.h`): `is_armor`, `is_suit`, `is_cloak`, `is_shield`,
     `is_helmet`, `is_gloves`, `is_boots`, `is_shirt`;
     `armor_slot(obj) -> int` (the `W_*` bit from `oc_armcat`, 0 otherwise);
   - `setworn(mon, item, mask)` (C `setworn` over the inventory; clears the
     slot on the displaced item; intrinsic hooks STUB);
   - `which_armor(world, mon, mask) -> Optional[Item]` (C `which_armor`);
   - `wearing_armor(mon) -> bool` (C `invent.c` `wearing_armor`);
   - `arm_bonus(obj) -> int` (C `ARM_BONUS`; 0 for non-armor; uses
     `weapon.greatest_erosion`);
   - `ac_bonus(world, mon) -> int` (Σ `arm_bonus` over the 7 slots + `spe`
     of worn `RIN_PROTECTION` rings + 2 for worn `AMULET_OF_GUARDING`);
   - `uac(world, mon, ublessed=0, uspellprot=0) -> int` (C `find_ac`
     computation; `AC_MAX = 99` clamp);
   - `ac_value(ac, rng) -> int` (C `AC_VALUE`; no draw when `ac >= 0`).
   - STUBs (raise `NotImplementedError`): `Boots_on/off`, `Cloak_on/off`,
     `Helmet_on/off`, `Shield_on/off`, `Shirt_on/off`, `Gloves_on/off`,
     `Armor_on/off` (intrinsic side effects — the property-system port),
     `welded`, `stop_donning`, `Amulet_on/off`, `Ring_on/off`
     (side effects), `disintegrate_arm`, `destroy_arm`, `inaccessible_equipment`,
     `count_worn_stuff`, `doddoremarm` (Phase 4 / property port / 'A' command).
4. `core/mhitu.py`:
   - `mattacku`: differential becomes
     `tmp = ac_value(worn.uac(world, hero), rng) + 10 + mdat.mlevel`
     (C `mattacku`);
   - `hitmu`: negative-AC damage reduction reads
     `worn.uac(world, hero)` instead of `hero.ac` (C `hitmu`).
5. Tests — `tests/test_worn.py` (new) + mhitu extensions:
   - `arm_bonus`: leather 2 / chain 5 / plate 3; `+3` spe; erosion cap
     (stand-in obj with `oeroded`, as `test_weapon.py` does); non-armor 0.
   - `ac_bonus`: each of the 7 slots independently; two protection rings;
     amulet of guarding +2; negative-spe ring worsens AC.
   - `uac`: base 10 with a full set (e.g. chain 5 + elven cloak 1 + helmet 1
     + shield 1 + gloves 1 + boots 1 = effective 1); clamp to −99/99 (unit
     the clamp step).
   - `ac_value`: positive identity with **no** `SeqRng` draw; negative
     `ac=-2` returns `−rnd(2)` (draw asserted).
   - `setworn`/`which_armor`/`wearing_armor`: don, replace (old mask
     cleared), empty slot, monster-shape reuse.
   - predicates against real table rows (leather armor, robe, small shield,
     leather gloves, low boots, Hawaiian shirt, elven leather helm).
   - `mattacku` with a geared hero: chain-mail hero (eff AC 5) vs goblin →
     threshold 17 (SeqRng: 16 hits, 17 misses); negative-AC hero → the
     `AC_VALUE` roll precedes the `d(20+i)` roll, and hitmu damage is
     reduced by `rnd(−ac)` with the min-1 floor.
   - Regression: the existing `test_mhitu.py` suite passes unmodified
     (hero ac 5, no gear → no new draws).

Acceptance: `pytest` green; a hero in chain mail takes measurably fewer
hits than a bare hero (AC 10) at the same monster level; demo seed-42
behaviour unchanged.

### Phase 2 — donning, doffing, pickup, commands, UI, demo gear

Tasks:

1. `core/commands.py`: `WearCommand(item_id)`, `TakeOffCommand(item_id)`,
   `PickupCommand()`; extend the `Command` union.
2. `core/worn.py` (don/doff half of `do_wear.c`):
   - `can_wear(world, mon, item) -> Optional[str]` (C `canwearobj` + the
     accessory checks in `accessory_or_armor_on`): already worn; suit over
     cloak; shirt under suit/cloak; slot filled per category; shield while
     wielding a `bimanual` weapon (via `items.wielded_of` +
     `weapon.bimanual`); twoweap (always False — noted); rings: left/right
     slots; amulet slot; non-wearable ("You cannot wear that!"). The
     polyform checks (`verysmall`/`nohands`/horns/hooves/foot-traps) are
     dead without polymorph — dropped, noted.
   - `dowear(world, mon_id, item_id, rng) -> List[Event]`: item must be in
     the hero's inventory; `can_wear`; `setworn`; C messages ("You are now
     wearing the X." / prinv-style lines for rings and the amulet); the
     per-type `<Type>_on()` call sites are STUB hooks.
   - `dotakeoff(world, mon_id, item_id, rng) -> List[Event]` (C
     `armor_or_accessory_off` + `select_off` subset): not-worn check; suit
     under cloak / shirt under suit-or-cloak layering; `cursed(item)` →
     "You can't. It is cursed."; clear slot; "You were wearing the X."
     (gloves-vs-welded and boot-trap checks are dead — noted).
3. `core/pickup.py` (new; C `pickup.c` `pickobj()` subset): topmost item on
   the hero's tile → inventory, "You pick up the X."; empty floor →
   "You see nothing here to pick up." (no merging, no cap, no leashes).
4. `core/step.py`: wire the three commands into the player turn.
5. `core/worldgen.py` (no new RNG draws):
   - hero: `ac=10`; starting inventory gains **chain mail (worn)**, leather
     cloak, leather gloves, ring of protection (+1) (carried, unworn);
   - floor: ~5 armour items (leather armor, elven leather helm, low boots,
     small shield, leather jacket) at fixed positions passed to
     `generate_map(keep_floor=...)` alongside `HERO_POS`.
6. `ui/console.py`:
   - inventory line: carried items with letters `a`, `b`, ... in inventory
     order, worn items marked (e.g. `🎒 [a: leather cloak] [b: leather gloves] [c: ring of protection (+1) *worn: chain mail*]`);
   - keys: `w<letter>` → `WearCommand`, `t<letter>` → `TakeOffCommand`,
     `g` → `PickupCommand`;
   - status line gains the effective AC (`🛡️ AC: n`, computed via
     `worn.uac`).
7. Tests:
   - `can_wear` table (item × worn-state → message/ok);
   - `dowear`/`dotakeoff` per slot: slot filled, replacement, AC before/
     after (`uac` asserts), message text; cursed doff blocked; layering
     errors both directions;
   - pickup: topmost item, nothing on the floor, floor item's `pos` cleared;
   - `step` integration: `WearCommand`/`TakeOffCommand`/`PickupCommand`
     through `step()` — events + resulting `uac`;
   - worldgen: seeded world — hero eff AC 5, chain mail worn, floor items
     on floor tiles (not walls, not the hero's tile); `test_step`
     same-seed test still green.

Acceptance: in the console game the hero can walk over to the leather
helmet, `g`, `wa` (or the chosen key scheme), watch the AC line drop, and
`ta` it back off again; cursed gear (add one cursed item to the floor for
the demo? optional) refuses to come off.

### Phase 3 — defence details from `mhitu.c`

1. Fill `mhitu.magic_negation(mon)` (C `mhitu.c`): max `a_can` over worn
   armour + 2 (amulet of guarding) / +1 (other Protection source — none in
   the subset) , capped at 3; uses `worn.which_armor` + the `OBJECTS` table.
   No live call site yet (hero-facing zaps/monster spells unported) — the
   function is real and tested; the call sites land with `castmu`/`zap`-on-
   hero. Update the mhitu docstring (STUB → implemented-with-pending-call-
   site).
2. Fill `mhitu.u_slip_free(mon, mattk)` (C `mhitu.c`): needs
   `Item.greased: bool = False` (C `obj->greased`); greased
   cloak→suit→shirt fallback, oilskin cloak, AT_ENGL excluded, cursed fails
   1/3, grease wears off 1/2 (message). Same "no live call site yet" note
   (no demo monster hugs/wraps).
3. Tests: `magic_negation` table (nothing → 0; leather 0; plate 2; plate +
   amulet → 3 cap; amulet alone → 2); `u_slip_free` table (greased cloak
   vs hug → true; vs engulf → false; no gear → false; cursed 1/3 fail with
   `SeqRng`; grease-wear-off message + `greased` flag cleared).

### Phase 4 — erosion & armour destruction (follow-up series)

1. `Item` gains `oeroded: int = 0`, `oeroded2: int = 0`,
   `oerodeproof: bool = False` (C `obj` fields).
2. Port `erosion_matters()` (`objnam.c`), `obj_erode_type()`
   (`do_wear.c`), the material predicates (`obj.h`: `is_flammable`,
   `is_rustprone`, `is_crackable`, `is_rottable`, `is_corrodeable` — over
   `Object.material`/class), `ERODE_*` constants, `MAX_ERODE`, and
   `erode_obj()` (`trap.c`, hero-facing subset: message, `spe`/`oeroded`
   decrement, destruction at max, AC recalculation is free via computed
   `uac`).
3. Call sites: acid splash (the `passiveum` acid branch already anticipates
   `erode_armor`), fire damage to worn gear, and a destroy-armor
   scroll path (`SCR_DESTROY_ARMOR` → `disintegrate_arm`, C
   `do_wear.c` — fill the Phase-1 STUB).
4. Tests: erosion per material type, enchantment erosion, destruction drops
   the item (floor) or clears the slot (worn, message), `ARM_BONUS` drops
   with erosion, `uac` follows.

### Phase 5 — explicitly NOT planned (future, listed so nobody re-decides)

- Intrinsic/extrinsic property system (`u.uprops[]`) — unlocks all
  `<Type>_on/off` side effects, cloaks of protection → `ublessed`,
  `magic_negation`'s Protection path.
- Monster armour (`mon.c` `minvent`, `m_dowear`, `misc_worn_check`).
- Multi-turn don/doff (`nomul`/occupations), the `'A'` take-off-all command
  (`takeoff_order`, `count_worn_stuff`, `doddoremarm`).
- Identification (`known`/`bknown`/`dknown`, enchantment revelation).
- Welded/cursed-weapon interactions, `uskin`, dragon-skin merging.
- Wielding unified onto `owornmask` (`W_WEP`).

---

## 4. Files touched

| File | Change |
|---|---|
| `core/objects.py` | `W_*` masks (prop.h) |
| `core/types.py` | `Item.owornmask` (+`greased` Ph3, `oeroded*` Ph4); `Monster.ac` docstring (base AC) |
| `core/worn.py` | **new** — Phase 1 (AC core), Phase 2 (don/doff), Phase 4 (erosion entry points) |
| `core/pickup.py` | **new** — Phase 2 |
| `core/mhitu.py` | differential via `AC_VALUE`/`uac`; negative-AC reduction via `uac`; Ph3 fill `magic_negation`/`u_slip_free` |
| `core/commands.py` | `WearCommand`, `TakeOffCommand`, `PickupCommand` |
| `core/step.py` | wire the three commands |
| `core/worldgen.py` | `HERO_BASE_AC = 10`, starting gear, floor armour (fixed positions via `keep_floor`) |
| `ui/console.py` | inventory line, `w/t/g` keys, AC in status line |
| `tests/test_worn.py`, `tests/test_pickup.py` | **new** |
| `tests/test_mhitu.py` | AC-integration tests |
| `tests/test_step.py`, `tests/test_worldgen.py` | (only if seeded expectations shift — expected: none) |
| `ARCHITECTURE.md`, `README.md` | layout, behaviour decisions, keys — updated per phase |

Commit granularity: one commit per task (house style), phases land in
order; Phase 1 must be green before Phase 2 starts touching `step`/`ui`.

---

## 5. Risks / open questions (flag for the execution session)

1. **Hero base AC = 10 vs keeping 5.** Decision above: 10 + starting chain
   mail (effective 5). If the user prefers "naked 5 + gear on top", it's a
   one-line worldgen change, but it diverges from C and the `find_ac`
   transcription. → Confirm before Phase 1.
2. **Key scheme for item selection.** `w<letter>`/`t<letter>` on the
   single-line input is the smallest UI change; an alternative is a
   selection menu (bigger). → Confirm before Phase 2 UI.
3. **Cursed gear in the demo.** `Item.cursed` exists; no demo item is
   cursed yet. Adding one cursed floor item (e.g. a cursed cloak) makes the
   "You can't. It is cursed." path reachable in play. Optional; default yes.
4. **Pickup scope creep.** C `pickup.c` is huge; the subset (topmost item,
   no merge/cap/leash) is deliberately tiny. Resist adding "pick up all"
   (`'G'`) in this pass.
5. **Draw-order discipline.** Every new `rnd`/`d` call changes `SeqRng`
   expectations; keep the Phase-1 `AC_VALUE` draw strictly inside
   `ac_value()` so it is the single auditable draw for negative AC.


---
