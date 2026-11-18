# HANDOFF

## 1. Task & scope
Port NetHack (C, cloned at `../NetHack`) to pyhack, following the
PLAN-*.md specs and ARCHITECTURE.md's "Suggested next steps" queue.
This session executed queue item 1's seventh staging: **Wave 5, phase
4d (PLAN-SPECIAL-ROOMS.md) — the shop's behaviour: the dialogue, the
`shkname` honorific, the keeper's movement, and the anger state
machine.**  That closes the `shk.c` port: the keeper now speaks
(`shk_entered` / `shk_left` on the `track_shop` hook, `shk_chat` behind
the `TalkCommand`), is addressed by honorific (Mr. / Ms. from the
name-prefix gender codes, replacing the `_shk_bare_name` stopgap in the
4c messages), moves (the `following` chase after a robbery, the angry
pursuit, the way home — the greedy single step in core.step's monster
turn), and is settled by the anger state machine
(`angry_shk_exists` / `rouse_shk` / `pacify_shk` / `make_happy_shk`
around 4c's `rile_shk`; `do_pay` pays the full robbery and calms the
keeper).  Only the vault (phase 5, optional) remains of the plan.

## 2. Status
**Done (this session, to commit):** `core/shk.py` gained the behaviour
section (the C spans are in the module docstring): `shkname` (shknam.c
855 + the call-site honorific, end.c 268-272 — the prefix codes
shknam.c 21-30: PERSONAL names take no honorific, GENERAL names do, by
`Monster.female`; the 4c messages — the robbery, the door block, the
do_pay closing line, the inheritance — now use it, the "in Mr. X's
general store" compounds take C's possessive `s_suffix`), `shk_entered`
(C: u_entered_shop 750-917 — the DESERTED line (C deserted_shop 721:
"is deserted" / "is untended" / "seems to be untended" by the monster
counts, the sensed half via the hero's sight), the new-customer reset
(visitct / following / `pacify_shk(TRUE)`, the single-player reduction
of the plname comparison), no dialog while sleeping / following, then
the anger / surcharge / robbed / welcome lines (the welcome carries the
visitct " again")), `shk_left` (C: u_left_shop 578-625 — "Please pay
before leaving." / "Don't you leave without paying!" by the surcharge;
fires on a tracked leave BEFORE the 4c robbery's lines), `shk.talk`
(C: talk.c's dotal reduced to the shopkeeper half: the keeper of the
shop the hero stands in, failing that an adjacent keeper) + `shk_chat`
(C 5542-5623 — C's branch ladder in C's order: the anger lines, the
pursuit, the BILL TOTAL, the debit, the credit, the robbery, the
surcharge, the purse lines under 50 / over 4000, the shoplifters
fallback, the animated-statue half for a non-keeper), `shk_target` (C:
shk_move 4901-5015, the target half: the following chase, the angry
pursuit when the keeper sees the hero, the way home, stand still at
home), and the anger state machine `angry_shk_exists` (1343) /
`pacify_shk` (1356 — the (price+3)//4 undo of the (price+2)//3 markup,
a 100 -> 133 -> 100 round trip) / `rouse_shk` (1393 — the sleep half of
C's helpless) / `make_happy_shk` (1407 — the anger and the pursuit
clear, the robbery is forgiven, a keeper off its square is set on it
again with the "calms down" / "returns to its shop" lines; home_shk
reduced to a square set).  `track_shop` fires the greeting / the leave
warning; `core/step.py`: the `TalkCommand` dispatch and the `isshk`
branch of the monster turn (the greedy single step onto
`shk_target`, before the wander — a keeper never random-walks);
`do_pay` ends with `make_happy_shk` (the 4b pay-all now also pays the
full robbery when the keeper is angry / following — C's dopay robbery
branch reduced to pay-all); `core/commands.py` + `ui/console.py`: the
`TalkCommand` (`t`; a lone `t` — `t`+letter still takes off);
`core/types.py`: the two new `Eshk` fields (`visitct` / `customer`, the
fixed stand-in "hero").  Tests — 28 new in tests/test_shop.py's 4d
section.  Docs (the plan's 4d record + status header + the §1 rows +
the DoD 4d line + the stale 4b note, CHANGES, the ARCHITECTURE shop
bullet + queue item 1, the module docstring).  1361 tests green, mypy
clean over 102 files, flake8 clean.  The demo path is untouched (it
never calls makelevel with specials=True, so no shop exists and the
new hooks are no-ops).

**Done (earlier, committed):** phase 1 — the temple (core/priest.py);
phase 2 — the zoo family; phase 3 — the swamp (+ core.engrave); phase
4a — a stocked shop (core/shknam_data.py + core/shk.py + mkshop);
phase 4b — the billing half (the price chain, the bill model, the Pay
command); phase 4c — the police (the robbery, the door block, the
surcharge, the EF_PAY reprice, the death-time inheritance).

**Not done (the rest of Wave 5, in the plan's order):**
- **Phase 5 — the vault** (~1 session, optional here): `create_vault`
  + the `VAULT` fill branch (phase 2.4) gives the room and the hoard;
  the **guard** (`src/vault.c`: `invault`, `gd_move`, `fakecorr[]`,
  `paygd`) is a separate system and stays out of scope — without it a
  vault is "a secret room full of gold", which is most of the fun and
  none of the cost.
- Interleaveable from the ARCHITECTURE queue: item 2 (the genesis
  residue — `m_initweap` / `m_initinv`, `splitobj` + merge rules, the
  mkobj_erosions residue), item 4 (wire QuaffCommand), item 5 (scrolls
  STUBs).

## 3. Files to read first
1. `PLAN-SPECIAL-ROOMS.md` — the status header + **phase 4d as
   rewritten (the record of what landed and why, including the named
   skips)** + phase 5 (the next work) + §5 (the deliberate
   divergences) + §6 (the traps).
2. `core/shk.py` — the behaviour section (`shkname` from the police
   section on: `shk_chat` / `talk` / `shk_entered` / `_deserted_line` /
   `shk_left` / `shk_target`, the anger machine `angry_shk_exists` /
   `rouse_shk` / `pacify_shk` / `make_happy_shk` around `rile_shk`, the
   `track_shop` greeting / leave warning, the `do_pay` settling) + the
   module docstring's "what this phase deliberately leaves out" list
   (now the 4d skip list).
3. `core/step.py` — the two 4d hooks: the `TalkCommand` dispatch and
   the `isshk` branch of `_monster_turn` (the `shk_target` step before
   the wander).
4. `tests/test_shop.py` — the 4d section (28 tests) and the 4a/4b/4c
   shapes (`_room_map` / `_FixedRng` / `_stocked_shop` / `_billed_shop`
   / `_inside_shop_pos` / `_bill_item`).
5. The C spans — via the c_function_index tooling, never a C file
   whole: the vault is `src/mkroom.c` `create_vault` (the room) +
   `src/vault.c` (the guard, out of scope); `fill_special_room`'s VAULT
   gold branch already exists in core.mkroom (phase 2).

## 4. Key discoveries
- **The new-customer reset PACIFIES first.**  C's u_entered_shop fires
  the reset (`visitct = 0`, `following = 0`, `pacify_shk(TRUE)`) when
  the customer is new — BEFORE the greeting ladder — so a FRESH account
  entering an angry shop is welcomed, not dared-at (the dare-return /
  unwelcoming lines need an ESTABLISHED account, the customer already
  recorded — the fixed stand-in, so after the first entry / a robbery).
  The tests set `eshk.customer` accordingly; the reset test asserts the
  ladder lands on the robbed line (the robbery ledger survives the
  reset, as in C).
- **The leave warning and the robbery land on the SAME move** (the
  named collapse of C's boundary grace): C's in_rooms counts the door
  square as still inside, so the hero hears "Please pay before leaving"
  on the door and may turn back; pyhack's strictly-inside model
  (§5.6) makes the door square outside, so `track_shop`'s leave branch
  fires `shk_left` and then `rob_shop` in one move (the warning is the
  lead-in to the robbery's lines — the ordering is tested).
- **`shk_target` is the target half of C's shk_move; the movement is
  core.step's.**  The `isshk` branch of `_monster_turn` runs the greedy
  single step (`_step_toward`) onto the target — the same machinery as
  the other monsters' chase, so the keeper never random-walks.  C's
  ladder, reduced: a FOLLOWING keeper chases the hero (any distance),
  an ANGRY keeper that can see the hero (C: mcansee && m_canseeu — the
  hero's sight, `vision_recalc`d in step) pursues it, every other
  keeper walks HOME and stands once it gets there (C: the GDIST < 3
  return 0).  Named skips: M2_GREEDY gold pickup, the chase lines
  (followmsg throttle + the 1-in-9 rile roll), the door-stance logic
  (uondoor / badinv / avoid / satdoor / onlineu), shk_fixes_damage,
  after_shk_move.
- **The honorific is one composed function.**  C strips the prefix in
  `shkname()` and applies Mr. / Ms. at the call site (end.c 268-272)
  from the prefix codes (PERSONAL '-' / '+' / '=' take none, GENERAL
  '_' / '|' or no prefix do, by `Monster.female` — which nameshk set
  from the same codes); the port composes both halves (the
  HANDOFF's stopgap replacement), and the 4c messages use it.
  `_shk_bare_name` remains as the internal half it is built from.
- **`make_happy_shk` keeps the markup; the new-customer reset clears
  it.**  `pacify_shk` takes the flag: the reset passes True (the
  (price+3)//4 undo, a 100 -> 133 -> 100 round trip),
  `make_happy_shk` passes False (the marked-up prices are the shop's
  memory of the robbery — a satisfied keeper does not forget).
- **`do_pay`'s satisfaction (the 4d end of the 4b pay-all):** a
  following / robbed keeper is paid the full bill AND the full robbery
  in one `p` (C's dopay robbery branch reduced to pay-all — the
  partial-compensation / 1000-gold-appeasement / "after blood, not
  gold" branches are named skips), and `make_happy_shk` settles the
  keeper (the anger / pursuit clear, the robbery is forgiven, a keeper
  off its square goes home).
- **The seeded `_stocked_shop` test world has TWO mimics** (mon_4 at
  (5,5), mon_12 at (6,7)) and the keeper "Asidonhopo" (no prefix -> the
  general-name honorific "Mr. Asidonhopo", purse 3340 — in between the
  50 / 4000 purse lines, so the chat ladder's fallback is the
  shoplifters line).  The movement / talk tests keep the hero at
  (10,8) — not adjacent to keeper or mimics (a monster adjacent to the
  hero attacks instead of moving) — and the "returns home" test needs
  the keeper's own square (5,4) free, which it is.
- **The untended counts are the hero's sight.**  `_deserted_line`
  counts the monsters in the room (n) and the ones the hero can see
  (m, `mon_visible` — `could_see` from the hero's tile): n == 0 ->
  "is deserted", m < n -> "seems to be untended", m == n -> "is
  untended".  Before a `vision_recalc` nothing is seen (m == 0), which
  is how the test pins both halves without moving the hero.
- **No rng draw in the behaviour chain** (the dialogue, the movement's
  target choice and the anger machine are pure state; the movement's
  single step reuses the monster turn's existing `rng.choice`).  Two
  new `Eshk` fields only: `visitct` / `customer`.
- **Named skips (4d):** the C dopay "after blood, not gold" /
  1000-gold-appeasement / partial-compensation branches (the pay-all
  model pays the full robbery and the keeper calms), the C shk_move
  door-stance logic and chase lines, the M2_GREEDY gold pickup,
  shk_fixes_damage / repair_damage (no repair system), the C empty_shops
  once-per-game repeat suppression (a dead keeper's shop can say it is
  deserted again on each re-entry), the Deaf / muteshk alternate lines
  and the hero-name slots (svp.plname — the verbalized halves with the
  name dropped), the C u_left_shop newlev / leavestring half (a
  level-change / teleport leave is a named escape the police do not
  see), and the izchak line of shk_chat (no towns).
- The pytest tool's `paths` are relative to the workspace root and
  currently resolve to a container mount that doesn't see the files —
  run the full suite with no paths (as always).

## 5. Next steps
1. **Wave 5, phase 5: the vault** (PLAN-SPECIAL-ROOMS.md §Phase 5,
   ~1 session, optional): `create_vault` (src/mkroom.c) + the `VAULT`
   fill branch (the gold per square; the dispatcher half already
   exists in core.mkroom.fill_special_room, phase 2).  The **guard**
   (src/vault.c: `invault`, `gd_move`, `fakecorr[]`, `paygd`) is a
   separate system and stays out of scope — without it a vault is "a
   secret room full of gold".  Verify the vault's room shape against
   the span before porting (the plan's trap: read the span, not the
   session summaries).
2. Same commit: the plan's phase-5 record + status header + DoD line,
   the CHANGES.md entry, and this HANDOFF rewritten for what follows
   (the queue items below).
3. Interleaveable: the genesis residue (queue item 2 — `m_initweap` /
   `m_initinv`, `splitobj` + the merge rules, the mkobj_erosions
   residue), the QuaffCommand wire-up (item 4 — `q` quits, so the quaff
   key is to choose), the scrolls STUBs (item 5 — SCR_DESTROY_ARMOR
   around the already-real `worn.disintegrate_arm`, SCR_LIGHT,
   SCR_CONFUSE_MONSTER).
4. Keep HANDOFF.md updated per the 5 sections above; keep every PLAN
   status header in sync in the same commit.
