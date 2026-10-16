# PLAN-RING.md: Porting Rings to PyHack

## 📐 Architectural Alignment
| NetHack C Concept | PyHack Python Target | Notes |
|-------------------|----------------------|-------|
| `struct obj *oleft/uright` | `Item` instances with `owornmask & (W_RINGL | W_RINGR)` | Already handled by `worn.py` |
| `Ring_on()` / `Ring_off()` | `rings.ring_on()` / `rings.ring_off()` | Will replace the `Ring_on/off` STUBs in `worn.py` |
| `adjust_attrib()` | `rules.adjust_attrib()` | Modifies `world.hero.attrib`, returns `[MessageEvent]` |
| `learnring()` | `rings.learnring()` | Discovery logic, updates `Item.dknown` & `Object.oc_name_known` |
| Per-turn effects (`allmain.c`) | `rules.tick_actor()` | Called from `step.py`; handles Regen, Teleportitis, Hunger, Polymorph |
| Conflict (`monmove.c`) | `step.py` (monster movement) | Triggers adjacent monster attacks |
| Object naming (`objnam.c`) | `items.py` / `objects.py` | `xname()` logic for rings |
| Generation (`mkobj.c`) | `worldgen.py` | Chances, charges, cursed/negative enchantment |
| Jade shuffle (`o_init.c`) | `o_init.py` | Class-wide description randomization |

---

## 📦 Phase 1: Core Ring Registry & Data (`rings.py`)
Create a new module `pyhack/core/rings.py` to keep `worn.py` focused on slot mechanics.

1. **Constants & Ranges**:
   ```python
   _RING_FIRST = ObjType.RIN_ADORNMENT
   _RING_LAST = ObjType.RIN_PROTECTION_FROM_SHAPE_CHAN
   ```
2. **`learnring(ring: Item, observed: bool) -> None`**:
   - Port from `do_wear.c`. Updates `ring.dknown`, `Object.oc_name_known`, and emits `MessageEvent` for discovery.
3. **`adjust_attrib(world: World, ring: Item, attr: str, delta: int) -> List[Event]`**:
   - Modifies `world.hero.attrib[attr]`. Returns messages like `"You feel your strength increase."`
4. **`toggle_stealth(world: World, ring: Item, on: bool) -> List[Event]`**:
   - Handles `RIN_STEALTH`. Updates a `world.hero.is_stealthy` flag or similar. Emits quiet footsteps messages.

---

## ⚙️ Phase 2: Ring Effects Registry & On/Off Logic (`rings.py`)
Implement the switch/case logic for each ring type, returning events and mutating `World`.

```python
RING_EFFECTS = {
    ObjType.RIN_LEVITATION: "levitation",
    ObjType.RIN_STEALTH: "stealth",
    ObjType.RIN_WARNING: "warning",
    ObjType.RIN_SEE_INVISIBLE: "see_invisible",
    ObjType.RIN_INVISIBILITY: "invisibility",
    ObjType.RIN_PROTECTION: "protection",
    ObjType.RIN_GAIN_STRENGTH: "str",
    ObjType.RIN_GAIN_CONSTITUTION: "con",
    ObjType.RIN_ADORNMENT: "cha",
    ObjType.RIN_INCREASE_ACCURACY: "hit_bonus",
    ObjType.RIN_INCREASE_DAMAGE: "dmg_bonus",
    ObjType.RIN_PROTECTION_FROM_SHAPE_CHAN: "shape_res",
    ObjType.RIN_FIRE_RESISTANCE: "fire_res",
    ObjType.RIN_COLD_RESISTANCE: "cold_res",
    ObjType.RIN_SHOCK_RESISTANCE: "shock_res",
    ObjType.RIN_POISON_RESISTANCE: "poison_res",
    ObjType.RIN_FREE_ACTION: "free_action",
    ObjType.RIN_CONFLICT: "conflict",
    # ... other rings
}
```

**`ring_on(world: World, mon: Monster, ring: Item) -> List[Event]`**:
- Matches C's `Ring_on()` switch.
- Handles `float_up()`, `see_monsters()`, `set_mimic_blocking()`, `adjust_attrib()`, intrinsic toggles (`world.hero.props[prop] |= W_RING`).
- Calls `ac_bonus()` recomputation if `RIN_PROTECTION` is worn.

**`ring_off(world: World, mon: Monster, ring: Item) -> List[Event]`**:
- Matches C's `Ring_off_or_gone()`.
- Reverses attributes, clears intrinsics, calls `float_down()`, updates visibility.

---

## 🔄 Phase 3: Per-Turn & Passive Effects (`rules.py` / `step.py`)
Port the tick-based and movement-based effects.

1. **`tick_ring_effects(world: World, mon: Monster) -> List[Event]`**:
   - Scans worn rings. Calls per-type tick functions.
   - `RIN_REGENERATION`: Heals 1 HP/turn (if not at max).
   - `RIN_TELEPORTATION`: Chance to teleport hero (or nearby monster).
   - `RIN_HUNGER`: Accelerates hunger penalty (eats more food/turn).
   - `RIN_POLYMORPH`: Chance to polymorph hero (calls existing poly system).
2. **`conflict_effect(world: World) -> List[Event]`**:
   - Ported from `monmove.c`. If a hero wears `RIN_CONFLICT`, adjacent monsters attack each other instead of the hero.

---

## 🛍️ Phase 4: Generation & Naming (`worldgen.py` / `items.py` / `o_init.py`)
1. **Generation (`worldgen.py`)**:
   - Port `mksobj()` RING_CLASS branch: `blessorcurse(otmp, 3)`.
   - Spe calculation: `rn2(2) ? rne(3) : -rne(3)`. If `spe == 0`, roll `rn2(4) - rn2(3)`.
   - Negative spe often implies curse.
2. **Naming (`items.py`)**:
   - Update `xname()` logic for `ObjClass.RING`. Handles `"ring of %s"`, `"cursed/blessed ring of %s"`, worn suffix `"(on left/right hand)"`.
3. **Shuffle (`o_init.py`)**:
   - Port `shuffle(svb.bases[RING_CLASS], ...)` to randomize unidentified descriptions at startup.

---

## 🔌 Phase 5: Wiring into `worn.py`
Replace the existing `Ring_on`/`Ring_off` STUBs in `worn.py` with calls to the new `rings.ring_on()` and `rings.ring_off()`.

```python
# In worn.py, inside _type_on() / _type_off()
def _type_on(world, mon, item, mask):
    if mask & W_RING:
        return ring.ring_on(world, mon, item)
    # ... existing armor/amulet hooks
```

---

## ✅ Implementation status (what the tests must target)

**Implemented and live:**
- `core.events.DiscoveryEvent` + `core.rules.apply_discovery` (the choke point) + routing in `process_events`.
- `World.obj_tables` (a per-game `o_init.ObjTables` owning its own deterministic rng stream) + `Item.dknown` / `Item.known`.
- `core.rules.current_ability` (computed, never cached: base + the spe of the worn ability rings).
- `core.rings`: `is_ring`, `learnring` (producer → `DiscoveryEvent`), `ring_on` / `ring_off` (the C `Ring_on` / `Ring_off_or_gone` switch as a producer), `tick_rings` (regen + teleport per turn), `ring_name`.
- `core.worn`: `_type_on` / `_type_off` dispatch rings to `core.rings`; `Ring_on` / `Ring_off` now delegate to `core.rings`; `dowear` / `dotakeoff` run their events through `process_events` (so the discovery is applied in the core).
- `core.step`: `tick_rings` runs for the hero + each monster after the status tick.
- `core.uhitm`: the to-hit `abon` reads `current_ability` (a worn STR/DEX ring feeds to-hit).

**STUBs (the ACTIVE effect is deferred; DISCOVERY still works — test for discovery + prop conveyance, NOT the effect):** levitation, stealth, invisibility, see-invisible, warning, searching (see the `core.rings` module docstring for the full list); per-turn hunger (no hunger system) and polymorph (no poly system); accuracy / damage (the `u.uhitinc` / `u.udaminc` melee bonuses — the full uhitm port).

**NOT implemented (deferred — do NOT write these tests yet):** ring generation (the mksobj RING branch / floor rings; the demo uses a fixed starting ring); the UI wiring of `ring_name` (the console still shows `Item.name`). The `o_init` description shuffle already exists — no new shuffle test is needed for rings.

> **Baseline note:** the working tree has PRE-EXISTING failures unrelated to rings. `tests/test_worldgen.py` had a literal `\n` corruption (now fixed); ~21 failures remain in test_spells / test_zap / test_weapon / test_vision / test_monst / test_scroll. Establish a clean baseline before adding the ring suite.

## 🧪 Phase 6: Testing — spec for `tests/test_rings.py`

Conventions (match `tests/test_worn.py`):
- Build ring items with the REAL table row (fine identity) so `is_ring`, `oprop`, `charged` and the discovery are exercised against the C values. Helper `_ring(otyp, spe=0, owornmask=0)` → `Item(otype=ObjectType.RING, otyp=int(otyp), oclass=int(ObjClass.RING), spe=...)`.
- `_add(w, mon, item)` carries it (`item.container = mon.id; mon.inventory.append(item); w.items[item.id] = item`).
- Worlds from `conftest.make_world` / `make_hero`; deterministic dice from `conftest.SeqRng`.
- The architecture under test: `ring_on` / `ring_off` are **producers** (they RETURN events and mutate nothing); the discovery mutation happens only in `core.rules.apply_discovery`, reached via `process_events` (from `dowear` / `dotakeoff`) or directly in a test. `tick_rings` is called by `step`.

### A. The discovery contract (the headline)
1. `test_ring_on_is_a_pure_producer` — the KEY architectural test:
   - `w = make_world()`; `ring = _add(w, hero, _ring(RIN_PROTECTION, spe=1))`.
   - `ev = rings.ring_on(w, hero, ring)`.
   - Assert `ev` contains exactly one `DiscoveryEvent` (otyp=RIN_PROTECTION, item_id=ring.id, mark_known=True, mark_encountered=True, reveal_spe=True).
   - Assert `ring.dknown is False` and `RIN_PROTECTION.value not in w.obj_tables.name_known` — i.e. `ring_on` mutated NOTHING.
   - Then `process_events(w, ev, SeqRng())` → assert `ring.dknown is True`, the type is in `name_known`, and `ring.known is True`.
2. `test_wearing_marks_seen` — any ring, after `dowear` (which applies the event), has `dknown True` and its type in `encountered`.
3. `test_learnring_branches` — table the C branches (assert the emitted `DiscoveryEvent` flags AND the post-`apply_discovery` state):
   - observed=True & type unknown → `mark_known` True (type discovered).
   - observed=True & type already known → type stays known (idempotent), item marked seen.
   - observed=False (a passive ring) & type unknown → type NOT discovered (seen only).
4. `test_enchantment_revealed_only_for_charged_known` — a charged ring (protection / gain-strength, `OBJECTS[typ].charged` True) that is both seen and type-known → `Item.known` True after apply; a non-charged ring (fire resistance) → `Item.known` stays False even when discovered.
5. `test_apply_discovery_is_idempotent` — applying the same `DiscoveryEvent` twice changes nothing the second time (dknown/known stay True; `name_known` / `encountered` / the `disco` order are unchanged).
6. `test_apply_discovery_looks_item_up_by_id` — a `DiscoveryEvent` whose `item_id` is not in `w.items` still updates the object table but touches no item (no crash).

### B. Ability rings (computed, never cached)
7. `test_current_ability_is_computed` — `hero.ustr == 12` base; wear a `RIN_GAIN_STRENGTH spe=2` (owornmask W_RINGL) → `current_ability(hero, "str") == 14`; doff → back to 12; a second worn ring of the same type adds on (16); a CARRIED (unworn) ring contributes nothing; CON → `ucon`, CHA (adornment) → `ucha` (both default 12); `current_ability` raises `ValueError` on an unknown key.
8. `test_attribute_messages` — table `(ring, spe, on_msg, off_msg)`: `RIN_GAIN_STRENGTH` +1 "You feel strong!" / −1 "You feel weak!", +2 "You feel very strong!" / −2 "You feel very weak!"; `RIN_GAIN_CONSTITUTION` tough / fragile; `RIN_ADORNMENT` charismatic / repulsive; spe 0 → no message at all (and observed False → seen only).
9. `test_str_ring_feeds_to_hit` — a hero wielding the short sword and wearing a `RIN_GAIN_STRENGTH spe=+5` (pushing STR 12→17, crossing the abon threshold) has a strictly higher `uhitm` to-hit threshold than the same hero without the ring (guards the `core.uhitm` integration point).

### C. Protection ring (AC is free via `uac`)
10. `test_protection_ring_moves_ac` — `uac` drops by `spe` when worn (left then right hand) and restores on doff; a `spe == 0` protection ring is seen only (observed False → no type discovery).
11. `test_two_protection_rings_stack` — left +2 and right +1 → `ac_bonus` +3, and the discovery fires once per hand.

### D. Per-turn effects (`tick_rings`)
12. `test_regen_tick` — hero hp 5/10 + worn `RIN_REGENERATION` → `tick_rings` → hp 6 and NO `MessageEvent` (silent, like C's botl update); at full hp → no change, no draw.
13. `test_teleport_tick` — hero + worn `RIN_TELEPORTATION`; a `SeqRng(1)` (so `randint(1,85)==1`) → the hero is teleported (pos changes, a `StatusEvent("teleport")` / the "teleported" message is present); a `SeqRng(85)` (a miss) → no move.
14. `test_tick_rings_draws_only_when_needed` — a `CountingRng` (record every `randint` / `choice` / `shuffle`): `tick_rings` on a ring-less hero makes ZERO draws; with a teleport ring it makes exactly ONE (a determinism guard for `step`).
15. `test_hunger_and_polymorph_are_stubs` — worn `RIN_HUNGER` / `RIN_POLYMORPH` → `tick_rings` returns `[]` and changes nothing (documents the deferred systems; the props ARE still conveyed via `worn_properties`).

### E. The passive / feel-it / stub rings
16. `test_passive_ring_conveys_its_prop` — for each of the resistance / free-action / slow-digestion / sustain / aggravate / conflict rings: worn → `has_property(world, hero, Prop.X)` True; doffed → False (the "works via core.props" half).
17. `test_feelit_rings_discover_on_wear` — levitation / stealth / invisibility / see-invisible: after `dowear`, the type is discovered (observed True) and `dknown` True, but NO active state is toggled (the effect is a stub — assert only the discovery events were produced).
18. `test_ring_range` — `is_ring` is True for `RIN_ADORNMENT .. RIN_PROTECTION_FROM_SHAPE_CHAN` and False for `AMULET_OF_GUARDING` / `CHAIN_MAIL` / a coarse-only item (otyp 0).

### F. Naming (`ring_name`)
19. `test_ring_name_unknown` → bare `"ring"` (type not known).
20. `test_ring_name_type_known` → `"ring of <name>"` (type known, enchantment not yet).
21. `test_ring_name_reveals_enchantment` → `"ring of protection (+1)"` / `"ring of gain strength (-2)"` once `Item.known` (charged + type known); a non-charged ring shows no `(+N)`.
22. `test_ring_name_reads_the_table` — with a fresh `ObjTables`, an undiscovered ring resolves through the (possibly shuffled) description; a discovered one through the real name.

### G. Don/doff wiring & event stream (integration)
23. `test_type_on_off_dispatch_rings` — `worn._type_on(world, hero, ring, W_RINGL)` returns `ring_on(...)`'s events; `worn._type_on` for a cloak returns `[]`.
24. `test_dowear_applies_discovery` — `worn.dowear(w, "player", ring.id, SeqRng())` on a +2 strength ring → the returned event stream is `[MessageEvent(on_msg), MessageEvent("You feel very strong!")]` (the `DiscoveryEvent` is consumed by the core, NOT in the returned list) AND `ring.dknown` / the type / `current_ability` are all updated.
25. `test_dowear_dotakeoff_round_trip` — wear then doff a protection ring through `step` (WearCommand / TakeOffCommand) → AC goes down then back, the messages are the C on/off lines, and the discovery state is consistent.

### H. Determinism / regression
26. `test_new_world_draw_sequence_unchanged` — keep the existing `test_new_world_makes_no_new_rng_draws` green (the `World.obj_tables` default uses its OWN `Rng(b"pyhack-objtables")`, so the seeded layout stream is untouched); add a check that a `step` on the ring-less demo hero makes no extra draws vs. before the ring port.

**Deferred (do NOT write yet — the feature is not implemented):** `test_ring_generation` (mksobj RING branch / cursed-neg-spe — no generator in the subset) and `test_conflict` (monster-vs-monster routing — the conflict effect is a stub).

---

## 📝 Execution Order (updated)
1. ✅ `core/rings.py` (Phases 1 & 2) — DONE.
2. ✅ Per-turn `tick_rings` + `step` wiring (Phase 3, the implemented half) — DONE.
3. ⏳ Phase 4 — the naming helper `ring_name` is DONE; generation + the full xname + UI wiring are DEFERRED.
4. ✅ Wire into `core/worn.py` (Phase 5) — DONE.
5. ⏳ Write `tests/test_rings.py` (the Phase 6 spec above) — NEXT.
6. ⏳ Fill the STUB active effects as their systems land (hunger, polymorph, levitation, stealth, invisibility, warning / search, accuracy / damage).

This keeps the ring *effects* isolated in `core.rings` (producers), the *discovery mutation* in the core (`apply_discovery`), and the per-turn upkeep in `step` — all on the event-driven `step()` model.
