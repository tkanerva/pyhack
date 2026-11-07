"""Tests for the experience & leveling system (core/experience.py, the
src/exper.c port) and the kill-XP gate in rules.apply_damage.

Table-driven over the C branches with SeqRng (exact rolls) and
dataclasses.replace over the committed MONS rows (the C permonst
table); the full-cave arc test runs the real demo world."""
import random
from dataclasses import replace

from conftest import SeqRng, make_world
from core.energy import init_energy
from core.events import DeathEvent, MessageEvent
from core.experience import (grant_kill_xp, init_experience,
                             kill_experience, losexp, more_experienced,
                             newexplevel, newhp, newuexp, pluslvl)
from core.mondata import M2_NASTY
from core.monst import (AD_DETH, AD_DRLI, AD_FIRE, AD_PHYS, AD_SLIM,
                        AD_STON, AD_WRAP, AT_BITE, AT_MAGC, AT_STNG,
                        AT_WEAP, Attack, MONS, PM_BAT, PM_GOBLIN,
                        PM_HILL_ORC, PM_MAIL_DAEMON, PM_VAMPIRE, S_EEL)
from core.rules import apply_damage
from core.types import (DamageType, Direction, Item, MAXULEV, Monster,
                        ObjectType, WandType)
from core.worldgen import new_world
from core.zap import use_wand


def demo_goblin(id="m_0", pos=(8, 4), hp=8, max_hp=8):
    """A PerMonst-typed goblin (the mdata-less conftest monsters are
    flat-stat: 1 XP, not the demo cave's 6)."""
    g = MONS[PM_GOBLIN]
    return Monster(id=id, name="Goblin", pos=pos, hp=hp, max_hp=max_hp,
                   ac=g.ac, mdata=g, m_lev=g.mlevel)


def xp_of(ptr, m_lev=None, ac=None):
    """The kill XP of a lone monster of PerMonst type `ptr` (the
    instance level pinned to the type level, as at spawn)."""
    mon = Monster(
        id="m_0", name=ptr.pmnames[2], pos=(8, 4), hp=10, max_hp=10,
        ac=ptr.ac if ac is None else ac, mdata=ptr,
        m_lev=ptr.mlevel if m_lev is None else m_lev)
    return kill_experience(make_world(monsters=[mon]), mon)


# ------------------------------------------------------------
# The level threshold (C: newuexp)
# ------------------------------------------------------------

def test_newuexp_threshold_table():
    assert newuexp(0) == 0            # the newuexp(ulevel - 1) guard
    assert newuexp(1) == 20
    assert newuexp(2) == 40
    assert newuexp(5) == 320
    assert newuexp(9) == 5120
    assert newuexp(10) == 10000
    assert newuexp(15) == 320000
    assert newuexp(19) == 5120000
    assert newuexp(20) == 10000000
    assert newuexp(21) == 20000000
    assert newuexp(30) == 110000000


# ------------------------------------------------------------
# The kill-XP formula (C: experience)
# ------------------------------------------------------------

def test_kill_experience_of_the_three_demo_cave_monsters():
    # PLAN-EXPERIENCE.md worked numbers
    assert xp_of(MONS[PM_GOBLIN]) == 6       # 1 + 0 + 5 (AT_WEAP)
    assert xp_of(MONS[PM_HILL_ORC]) == 10    # 1 + 4 + 5 (AT_WEAP)
    assert xp_of(MONS[PM_BAT]) == 6          # 1 + 0 + 5 (mmove 22 > 18)


def test_kill_experience_of_a_flat_stat_monster_is_one():
    mon = Monster(id="m_0", name="Flat", pos=(8, 4), hp=1, max_hp=1, ac=0)
    w = make_world(monsters=[mon])
    assert kill_experience(w, mon) == 1


def test_kill_experience_reads_the_instance_level():
    # m_lev is the INSTANCE level (the spawn-time pin), not the type
    g = MONS[PM_GOBLIN]                      # mlevel 0
    assert xp_of(g, m_lev=8) == 1 + 64 + 5
    assert xp_of(g, m_lev=9) == 1 + 81 + 5 + 50   # the m_lev > 8 bonus


def test_kill_experience_ac_bonus_branches():
    g = MONS[PM_GOBLIN]                      # ac 10: no bonus, base 6
    assert xp_of(replace(g, ac=2)) == 6 + 5  # (7 - 2) * 1
    assert xp_of(replace(g, ac=1)) == 6 + 6
    assert xp_of(replace(g, ac=0)) == 6 + 7
    assert xp_of(replace(g, ac=-1)) == 6 + 16   # (7 - -1) * 2 (negative)
    assert xp_of(replace(g, ac=3)) == 6        # i >= 3: no bonus


def test_kill_experience_speed_branches():
    g = MONS[PM_GOBLIN]                      # mmove 6: no bonus
    assert xp_of(replace(g, mmove=12)) == 6  # == NORMAL_SPEED: none
    assert xp_of(replace(g, mmove=13)) == 9  # > 12, <= 18: +3
    assert xp_of(replace(g, mmove=18)) == 9
    assert xp_of(replace(g, mmove=19)) == 11  # > 3*12/2: +5


def test_kill_experience_attack_type_bonuses():
    # C: the bonus is only for aatyp > AT_BUTT (the "special" types --
    # CLAW / BITE / KICK are not among them)
    g = MONS[PM_GOBLIN]                      # mlevel 0, ac 10
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_PHYS, 1, 4),))) == 1
    assert xp_of(replace(g, mattk=(Attack(AT_STNG, AD_PHYS, 1, 4),))) == 4
    assert xp_of(replace(g, mattk=(Attack(AT_WEAP, AD_PHYS, 1, 4),))) == 6
    assert xp_of(replace(g, mattk=(Attack(AT_MAGC, AD_PHYS, 1, 4),))) == 11


def test_kill_experience_damage_type_branches():
    g = replace(MONS[PM_GOBLIN], mattk=(Attack(AT_BITE, AD_PHYS, 1, 4),))
    assert xp_of(g, m_lev=2) == 1 + 4         # AD_PHYS: no bonus
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_FIRE, 1, 4),)),
                 m_lev=2) == 5 + 4            # elemental: +2*m_lev
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_DRLI, 1, 4),)),
                 m_lev=2) == 5 + 50           # DRLI / STON / SLIM: +50
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_STON, 1, 4),)),
                 m_lev=2) == 5 + 50
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_SLIM, 1, 4),)),
                 m_lev=2) == 5 + 50
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_DETH, 1, 4),)),
                 m_lev=2) == 5 + 2            # other non-physical: +m_lev
    # the heavy-damage bonus (damd * damn > 23)
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_PHYS, 1, 24),)),
                 m_lev=2) == 5 + 2
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_PHYS, 1, 23),)),
                 m_lev=2) == 5
    # the eel's wrap vs a non-amphibious hero: +1000
    eel = replace(g, mlet=S_EEL, mattk=(Attack(AT_BITE, AD_WRAP, 1, 4),))
    assert xp_of(eel, m_lev=2) == 5 + 2 + 1000
    # ...and a non-eel wrap gets only the non-physical half
    assert xp_of(replace(g, mattk=(Attack(AT_BITE, AD_WRAP, 1, 4),)),
                 m_lev=2) == 5 + 2


def test_kill_experience_extra_nasty_vampire():
    # 1 + 100 + 6 (ac 1) + 50 (AD_DRLI) + 70 (7*m_lev, M2_NASTY)
    # + 50 (m_lev 10 > 8)
    assert xp_of(MONS[PM_VAMPIRE]) == 277
    assert xp_of(replace(MONS[PM_VAMPIRE], mflags2=0)) == 277 - 70
    assert xp_of(replace(MONS[PM_VAMPIRE],
                         mflags2=M2_NASTY)) == 277


def test_kill_experience_mail_daemon_is_one():
    # C: MAIL_STRUCTURES, always defined in 5.0.  The row is absent from
    # the sparse MONS subset, so the branch is exercised through the
    # pmidx check alone (the formula's last line reads only it).
    assert xp_of(replace(MONS[PM_VAMPIRE], pmidx=PM_MAIL_DAEMON)) == 1


# ------------------------------------------------------------
# The XP accumulation (C: more_experienced)
# ------------------------------------------------------------

def test_more_experienced_is_silent_and_scales_score_x4():
    w = make_world()
    more_experienced(w, 6)
    assert w.hero.uexp == 6
    assert w.hero.urexp == 24
    more_experienced(w, 10, rexp=5)
    assert w.hero.uexp == 16
    assert w.hero.urexp == 24 + 4 * 10 + 5


def test_xp_gain_emits_no_message_like_c():
    w = make_world(monsters=[demo_goblin()])
    ev = apply_damage(w, "m_0", 8, DamageType.MELEE, "player")
    assert [e.text for e in ev if isinstance(e, MessageEvent)] == \
        ["Goblin takes 8 damage!", "☠️ Goblin dies!"]


# ------------------------------------------------------------
# The bookkeeping arrays (uhpinc / ueninc, the init slots)
# ------------------------------------------------------------

def test_init_records_the_init_bookkeeping_slots():
    w = make_world()
    init_energy(w, SeqRng(3))        # newpw(1) = 4 + 1 + 3 = 8
    init_experience(w)
    assert w.hero.uen == w.hero.uenmax == w.hero.uenpeak == 8
    assert w.hero.ueninc[0] == 8 and w.hero.ueninc[1] == 0
    assert w.hero.uhpinc[0] == 2     # base 2 + the CON 12 row (+0)


def test_newhp_is_base_two_plus_the_c_con_table():
    w = make_world()
    for con, expect in ((3, 1), (6, 1), (12, 2), (16, 3),
                        (17, 4), (18, 5), (19, 6)):
        w.hero.ucon = con
        assert newhp(w) == expect, con


# ------------------------------------------------------------
# The level-up (C: newexplevel / pluslvl)
# ------------------------------------------------------------

def test_level_up_at_the_threshold():
    w = make_world(monsters=[demo_goblin()])
    w.hero.uexp = 19
    ev = grant_kill_xp(w, w.actors["m_0"], SeqRng(2))
    h = w.hero
    assert h.ulevel == 2
    assert h.uexp == 25             # 25 < newuexp(2) = 40: no carry
    assert h.hp == h.max_hp == 27   # the draw-free newhp: +2
    assert h.uen == h.uenmax == h.uenpeak == 7  # newpw(1) = 4 + 1 + 2
    assert h.uhpinc[1] == 2
    assert h.ueninc[1] == 7         # the C newpw increment record
    assert h.ulevelmax == 2 and h.ulevelpeak == 2
    assert [e.text for e in ev if isinstance(e, MessageEvent)] == \
        ["Welcome to experience level 2."]


def test_level_up_carries_the_overflow_past_the_next_threshold():
    w = make_world(monsters=[demo_goblin()])
    w.hero.uexp = 199
    grant_kill_xp(w, w.actors["m_0"], SeqRng(1))
    assert w.hero.ulevel == 2
    assert w.hero.uexp == 39        # 199 + 6 = 205 >= 40: capped at 39


def test_no_level_up_below_the_threshold():
    w = make_world(monsters=[demo_goblin()])
    w.hero.uexp = 13
    ev = grant_kill_xp(w, w.actors["m_0"], SeqRng())
    assert ev == []
    assert w.hero.ulevel == 1
    assert w.hero.uexp == 19
    assert w.hero.hp == 25          # no HP / Pw change


def test_newexplevel_grants_at_most_one_level_per_call():
    # the AD&D rule (the exper.c comment): the overflow past the NEXT
    # threshold is forfeited, not re-rolled
    w = make_world()
    w.hero.uexp = 100000
    newexplevel(w, SeqRng(1))
    assert w.hero.ulevel == 2
    assert w.hero.uexp == 39


def test_level_up_draws_exactly_once_on_the_first_gain():
    class CountingRng:
        def __init__(self):
            self.count = 0

        def randint(self, a, b):
            self.count += 1
            return 2

    w = make_world(monsters=[demo_goblin()])
    w.hero.uexp = 19
    rng = CountingRng()
    grant_kill_xp(w, w.actors["m_0"], rng)
    assert rng.count == 1           # only the newpw(1) draw


def test_second_level_up_draws_nothing():
    w = make_world(monsters=[demo_goblin()])
    w.hero.ulevel = 2
    w.hero.uexp = 39                # newuexp(2) = 40
    w.hero.ueninc[1] = 7
    grant_kill_xp(w, w.actors["m_0"], SeqRng())   # any draw: IndexError
    h = w.hero
    assert h.ulevel == 3
    assert h.uexp == 45
    assert h.uen == 6               # newpw(2) = 4 + (2 - 1) * 2
    assert h.ueninc[2] == 6


def test_regaining_a_lost_level_welcomes_back():
    w = make_world(monsters=[demo_goblin()])
    w.hero.uexp = 19
    grant_kill_xp(w, w.actors["m_0"], SeqRng(1))
    assert w.hero.ulevelmax == 2
    losexp(w, "drained by a wraith")
    assert w.hero.ulevel == 1
    w.hero.uexp = newuexp(1)        # 20: crosses the threshold
    ev = newexplevel(w, SeqRng(1))  # the L1 -> 2 newpw draw
    assert [e.text for e in ev if isinstance(e, MessageEvent)] == \
        ["Welcome back to experience level 2."]


def test_pluslvl_non_incr_is_the_potion_path():
    w = make_world()
    w.hero.uen = w.hero.uenmax = w.hero.uenpeak = 7
    ev = pluslvl(w, False, SeqRng(2))
    h = w.hero
    assert h.ulevel == 2
    assert h.uexp == newuexp(1)     # the non-incr uexp set
    assert h.uen == h.uenmax == h.uenpeak == 14
    assert [e.text for e in ev if isinstance(e, MessageEvent)] == \
        ["You feel more experienced.",
         "Welcome to experience level 2."]


def test_pluslvl_at_max_level_gains_stats_but_no_level():
    w = make_world()
    w.hero.ulevel = MAXULEV
    w.hero.uexp = 12345
    ev = pluslvl(w, True, SeqRng())
    assert w.hero.ulevel == MAXULEV
    assert w.hero.uexp == 12345
    assert w.hero.max_hp == 27
    assert w.hero.uenmax == 60      # newpw(30): the table's top
    assert ev == []


def test_newexplevel_at_max_level_stays():
    w = make_world()
    w.hero.ulevel = MAXULEV
    w.hero.uexp = 10 ** 9
    assert newexplevel(w, SeqRng()) == []
    assert w.hero.ulevel == MAXULEV


# ------------------------------------------------------------
# The kill-XP gate (rules.apply_damage, C: the mkill kill path)
# ------------------------------------------------------------

def test_melee_kill_by_the_hero_grants_xp():
    w = make_world(monsters=[demo_goblin()])
    ev = apply_damage(w, "m_0", 8, DamageType.MELEE, "player")
    assert w.hero.uexp == 6
    assert any(isinstance(e, DeathEvent) and e.by == "player" for e in ev)


def test_zap_kill_by_the_hero_grants_xp():
    # decision 4: the zap damage source is the caster id, so a zap kill
    # flows through the same gate as a melee kill
    mon = demo_goblin(hp=3, max_hp=3)
    w = make_world(monsters=[mon])
    wand = Item(id="wand_0", otype=ObjectType.WAND, name="Wand",
                spe=1, wand_type=WandType.DEATH, carrier="player")
    w.items["wand_0"] = wand
    w.hero.inventory.append(wand)
    # the range roll (7 + 1), then the six d6 (all ones: 6 >= 3 hp)
    ev = use_wand(w, "player", WandType.DEATH, Direction.E,
                  SeqRng(1, 1, 1, 1, 1, 1, 1))
    assert not mon.alive
    assert w.hero.uexp == 6
    assert any(isinstance(e, DeathEvent) and e.by == "player" for e in ev)


def test_non_hero_kills_grant_no_xp():
    for source in ("m_1", "trap:trap_0", "poison"):
        w = make_world(monsters=[demo_goblin(),
                                 demo_goblin(id="m_1", pos=(9, 4))])
        apply_damage(w, "m_0", 8, DamageType.MELEE, source)
        assert w.hero.uexp == 0, source


def test_hero_death_grants_no_xp():
    w = make_world(monsters=[demo_goblin()])
    apply_damage(w, "player", 25, DamageType.MELEE, "m_0")
    assert not w.hero.alive
    assert w.hero.uexp == 0


def test_full_cave_clear_is_sixty_two_xp_reaching_level_three():
    # the demo arc: 4 goblins (6) + 2 orcs (10) + 3 bats (6) = 62 XP --
    # level 2 at the 4th kill (24 >= 20), level 3 at the 9th (62 >= 60)
    w = new_world(random.Random(42))
    pw_before = w.hero.uenmax
    kills = (["goblin_%d" % i for i in range(4)]
             + ["orc_%d" % i for i in range(2)]
             + ["bat_%d" % i for i in range(3)])

    class OneDraw:
        def __init__(self):
            self.count = 0

        def randint(self, a, b):
            self.count += 1
            return 2

    rng = OneDraw()
    welcomes = []
    for mid in kills:
        mon = w.actors[mid]
        ev = apply_damage(w, mid, mon.hp, DamageType.MELEE, "player",
                          rng=rng)
        welcomes += [e.text for e in ev if isinstance(e, MessageEvent)
                     and "Welcome" in e.text]
    h = w.hero
    assert h.ulevel == 3
    assert h.uexp == 62
    assert h.hp == h.max_hp == 29   # 25 + 2 + 2 (the draw-free newhp)
    assert h.uenmax == pw_before + 7 + 6   # the two level-up gains
    assert welcomes == ["Welcome to experience level 2.",
                        "Welcome to experience level 3."]
    assert rng.count == 1           # only the L1 -> 2 newpw draw


# ------------------------------------------------------------
# The level-loss (C: losexp)
# ------------------------------------------------------------

def level_two_hero():
    w = make_world()
    h = w.hero
    h.ulevel = 2
    h.hp = h.max_hp = 27
    h.uhpinc[1] = 2                 # the L1 -> 2 increment
    h.ueninc[1] = 7
    h.uen = h.uenmax = h.uenpeak = 7
    h.uexp = 45
    return w


def test_losexp_drains_one_level():
    w = level_two_hero()
    ev = losexp(w, "drained by a wraith")
    h = w.hero
    assert h.ulevel == 1
    assert h.max_hp == 25           # 27 - uhpinc[1]
    assert h.hp == 25
    assert h.uenmax == 0 and h.uen == 0      # 7 - ueninc[1], floor 0
    assert h.uexp == 19             # newuexp(1) - 1
    assert any(e.text == "Goodbye level 2." for e in ev)


def test_losexp_floors_uhpmax_at_the_lifesaving_minimum():
    w = level_two_hero()
    w.hero.uhpinc[1] = 20           # 27 - 20 = 7 -> min(ulevel, 10)
    losexp(w, "drained by a wraith")
    assert w.hero.max_hp == 10


def test_losexp_at_level_one_with_drainer_is_fatal():
    w = make_world()
    w.hero.uexp = 19
    ev = losexp(w, "drained by a wraith")
    assert not w.hero.alive
    assert any(isinstance(e, DeathEvent)
               and e.by == "drained by a wraith" for e in ev)
    assert any(e.text == "Goodbye level 1." for e in ev)


def test_losexp_at_level_one_without_drainer_resets_xp():
    # divine anger (C: losexp(NULL)): the XP reset, not fatal, and the
    # "Goodbye level 1." message is suppressed (C comment)
    w = make_world()
    w.hero.uexp = 19
    ev = losexp(w, None)
    assert w.hero.alive
    assert w.hero.ulevel == 1
    assert w.hero.uexp == 0
    assert all("Goodbye" not in e.text
               for e in ev if isinstance(e, MessageEvent))


def test_losexp_levelchange_is_never_fatal():
    # the wizard-mode override: drainer neutralized, the level-1 reset
    w = make_world()
    w.hero.uexp = 19
    ev = losexp(w, "#levelchange")
    assert w.hero.alive
    assert w.hero.ulevel == 1
    assert w.hero.uexp == 0
    assert all("Goodbye" not in e.text
               for e in ev if isinstance(e, MessageEvent))
