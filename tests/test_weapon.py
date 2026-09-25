"""Tests for the weapon port (core.weapon).

Focus: the algorithms -- hit/damage bonus computation (including RNG
draw order), the strength/dexterity bonus tables, and the skill-slot
economy.  Naming tables are not pinned here.
"""
from dataclasses import dataclass, replace

from core.mondata import hates_blessings, hates_silver
from core.monst import (M1_THICK_HIDE, MONS, PM_GARTER_SNAKE, PM_GOBLIN,
                        PM_GRAY_DRAGON, PM_GHOST, PM_NAMES,
                        PM_STONE_GOLEM, PM_VAMPIRE)
from core.objects import (Material, ObjType as O, OBJECTS, PIERCE,
                          Skill, WHACK)
from core.weapon import (
    DefSkill, P_BASIC, P_EXPERT, P_MASTER, P_SKILLED, P_UNSKILLED,
    P_GRAND_MASTER, RWERP, Skills, abon, advance_skill,
    add_weapon_skill, ammo_and_launcher, bimanual, can_advance,
    dbon, dmgval, drain_weapon_skill, hitval, is_ammo, is_axe,
    is_blade, is_blunt_weapon, is_graystone, is_launcher, is_multigen,
    is_pick, is_pole, is_spear, is_weptool, is_wet_towel,
    lose_weapon_skill, matching_launcher, peaked_skill, practice_needed,
    skill_init, use_skill, weapon_hit_bonus, weapon_dam_bonus,
    weapon_type,
)


@dataclass
class FakeObj:
    """Minimal struct-obj stand-in for the ObjLike protocol."""
    otyp: int
    oclass: int
    spe: int = 0
    blessed: bool = False
    owt: int = 0
    oeroded: int = 0
    oeroded2: int = 0
    globby: bool = False

    def __post_init__(self):
        if not self.owt:
            self.owt = OBJECTS[self.otyp].weight


def obj(name: str, **kw) -> FakeObj:
    t = O[name]
    return FakeObj(int(t), int(OBJECTS[int(t)].oclass), **kw)


@dataclass
class FakeMon:
    """Minimal struct-monst stand-in for the MonLike protocol."""
    mdata: object


class ScriptedRng:
    """Preset-value rng: rnd(x) == 1 + v % x, rn2(x) == v % x,
    d(n, x) == n + sum(v % x).  An exhausted script raises, which
    pins "this path consumes no dice"."""

    def __init__(self, *values):
        self.values = list(values)

    def rnd(self, x):
        return 1 + self.values.pop(0) % x

    def rn2(self, x):
        return self.values.pop(0) % x

    def d(self, n, x):
        return n + sum(self.values.pop(0) % x for _ in range(n))


goblin = FakeMon(MONS[PM_GOBLIN])
vampire = FakeMon(MONS[PM_VAMPIRE])
gray_dragon = FakeMon(MONS[PM_GRAY_DRAGON])
garter_snake = FakeMon(MONS[PM_GARTER_SNAKE])
stone_golem = FakeMon(MONS[PM_STONE_GOLEM])


# ------------------------------------------------------------
# weapon_type and the predicates that gate the algorithms
# ------------------------------------------------------------

def test_weapon_type():
    assert weapon_type(None) == Skill.P_BARE_HANDED_COMBAT
    assert weapon_type(obj("DAGGER")) == Skill.P_DAGGER
    assert weapon_type(obj("ARROW")) == Skill.P_BOW       # ammo: abs(-P_BOW)
    assert weapon_type(obj("CROSSBOW_BOLT")) == Skill.P_CROSSBOW
    assert weapon_type(obj("DIAMOND")) == Skill.P_SLING    # gems are sling ammo
    assert weapon_type(obj("PICK_AXE")) == Skill.P_PICK_AXE  # weptool
    assert weapon_type(obj("TOWEL")) == Skill.P_NONE
    assert weapon_type(obj("BOULDER")) == Skill.P_NONE
    assert weapon_type(obj("CREAM_PIE")) == Skill.P_NONE


def test_ammo_and_launcher_pairing():
    assert is_ammo(obj("ARROW")) and is_ammo(obj("SILVER_ARROW"))
    assert is_ammo(obj("CROSSBOW_BOLT"))
    assert is_ammo(obj("DIAMOND")) and is_ammo(obj("FLINT"))
    assert not is_ammo(obj("DART")) and not is_ammo(obj("SHURIKEN"))
    assert not is_ammo(obj("BOOMERANG")) and not is_ammo(obj("DAGGER"))
    assert is_launcher(obj("BOW")) and is_launcher(obj("YUMI"))
    assert is_launcher(obj("SLING")) and is_launcher(obj("CROSSBOW"))
    assert not is_launcher(obj("ARROW")) and not is_launcher(obj("DAGGER"))
    assert matching_launcher(obj("ARROW"), obj("BOW"))
    assert not matching_launcher(obj("ARROW"), obj("SLING"))
    assert not matching_launcher(obj("ARROW"), None)
    assert ammo_and_launcher(obj("CROSSBOW_BOLT"), obj("CROSSBOW"))


def test_strike_mode_and_material_predicates():
    assert is_weptool(obj("PICK_AXE")) and is_weptool(obj("UNICORN_HORN"))
    assert is_weptool(obj("GRAPPLING_HOOK"))
    assert not is_weptool(obj("TOWEL"))      # towel's oc_skill is P_NONE
    assert not is_weptool(obj("DAGGER"))     # not a tool
    assert bimanual(obj("BATTLE_AXE")) and not bimanual(obj("DAGGER"))
    assert is_blunt_weapon(obj("MACE")) and is_blunt_weapon(obj("CLUB"))
    assert is_blunt_weapon(obj("PICK_AXE"))  # weptool, WHACK
    assert not is_blunt_weapon(obj("DAGGER"))
    assert is_blade(obj("DAGGER")) and is_blade(obj("SCIMITAR"))
    assert not is_blade(obj("SPEAR")) and not is_blade(obj("MACE"))
    assert is_spear(obj("SPEAR")) and is_spear(obj("JAVELIN"))
    assert not is_spear(obj("DWARVISH_MATTOCK"))  # 5.0: mattock is not a spear
    assert is_pole(obj("HALBERD")) and is_pole(obj("LANCE"))
    assert not is_pole(obj("SPEAR"))
    assert is_multigen(obj("ARROW")) and is_multigen(obj("SHURIKEN"))
    assert not is_multigen(obj("SPEAR"))
    assert is_axe(obj("AXE")) and is_axe(obj("BATTLE_AXE"))
    assert not is_axe(obj("DWARVISH_MATTOCK"))
    assert is_pick(obj("PICK_AXE")) and is_pick(obj("DWARVISH_MATTOCK"))
    assert is_wet_towel(obj("TOWEL", spe=3)) and not is_wet_towel(obj("TOWEL"))
    assert is_graystone(obj("FLINT")) and is_graystone(obj("TOUCHSTONE"))
    assert not is_graystone(obj("ROCK")) and not is_graystone(obj("DIAMOND"))


# ------------------------------------------------------------
# hitval
# ------------------------------------------------------------

def test_hitval_base_and_enchantment():
    assert hitval(obj("DAGGER"), goblin) == 2      # oc_hitbon
    assert hitval(obj("DAGGER", spe=3), goblin) == 5
    assert hitval(obj("SPEAR"), goblin) == 0


def test_hitval_blessed_vs_blessing_haters():
    assert hates_blessings(vampire.mdata)
    assert hitval(obj("DAGGER", blessed=True), vampire) == 2 + 2
    assert hitval(obj("DAGGER"), vampire) == 2
    assert hitval(obj("DAGGER", blessed=True), goblin) == 2  # no bonus


def test_hitval_kebab_spears():
    assert hitval(obj("SPEAR"), gray_dragon) == 2
    assert hitval(obj("ELVEN_SPEAR"), gray_dragon) == 2
    assert hitval(obj("SPEAR"), goblin) == 0


def test_hitval_trident_vs_swimmers():
    assert hitval(obj("TRIDENT"), garter_snake, in_pool=True) == 4
    assert hitval(obj("TRIDENT"), garter_snake) == 2  # S_SNAKE out of water
    assert hitval(obj("TRIDENT"), goblin) == 0


def test_hitval_pick_vs_wallwalkers():
    pm = replace(MONS[PM_GHOST],
                 mflags1=MONS[PM_GHOST].mflags1 | M1_THICK_HIDE)
    # 4 = WHACK in the weptool's oc_hitbon slot (5.0) + 2 pick bonus
    assert hitval(obj("PICK_AXE"), FakeMon(pm)) == 4 + 2


def test_weptool_hitbon_is_strike_mode_in_5_0():
    # 5.0 WEPTOOL puts the strike mode in the oc_hitbon slot
    assert OBJECTS[int(O.PICK_AXE)].oc1 == WHACK
    assert OBJECTS[int(O.UNICORN_HORN)].oc1 == PIERCE
    assert hitval(obj("UNICORN_HORN"), goblin) == 1


# ------------------------------------------------------------
# dmgval
# ------------------------------------------------------------

def test_dmgval_cream_pie_consumes_no_dice():
    assert dmgval(obj("CREAM_PIE"), goblin, ScriptedRng()) == 0


def test_dmgval_base_and_enchantment():
    # small target: rnd(4) base for the dagger; preset 3 -> 1 + 3 % 4
    assert dmgval(obj("DAGGER"), goblin, ScriptedRng(3)) == 4
    assert dmgval(obj("DAGGER", spe=3), goblin, ScriptedRng(0)) == 1 + 3
    # negative enchantment mustn't produce negative damage
    assert dmgval(obj("DAGGER", spe=-5), goblin, ScriptedRng(0)) == 0


def test_dmgval_extra_damage_tables():
    # small: broadsword rnd(4) + rnd(4); presets 2, 1 -> 3 + 2
    assert dmgval(obj("BROADSWORD"), goblin, ScriptedRng(2, 1)) == 5
    # large: broadsword rnd(6) + 1; preset 5 -> 6 + 1
    assert dmgval(obj("BROADSWORD"), gray_dragon, ScriptedRng(5)) == 7
    # large: trident rnd(4) + d(2,4); presets 3, 0, 1 -> 4 + 3
    assert dmgval(obj("TRIDENT"), gray_dragon, ScriptedRng(3, 0, 1)) == 7
    # large: tsurugi rnd(8) + d(2,6); presets 0, 5, 5 -> 1 + 12
    assert dmgval(obj("TSURUGI"), gray_dragon, ScriptedRng(0, 5, 5)) == 13


def test_dmgval_thick_skinned_nullifies_flimsy_weapons():
    # towel (CLOTH <= LEATHER): 0 base damage, no dice at all
    assert dmgval(obj("TOWEL", spe=7), stone_golem, ScriptedRng()) == 0
    # dagger (IRON > LEATHER) is not nullified
    assert dmgval(obj("DAGGER"), stone_golem, ScriptedRng(5)) == 3


def test_dmgval_shade_ignores_non_glare_weapons():
    shade = FakeMon(replace(MONS[PM_GHOST], pmidx=PM_NAMES.index("shade")))
    assert dmgval(obj("DAGGER"), shade, ScriptedRng(3)) == 0


def test_dmgval_additive_bonuses_keep_rng_order():
    # silver dagger vs vampire: rnd(4) base + rnd(20) silver
    assert dmgval(obj("SILVER_DAGGER"), vampire, ScriptedRng(3, 9)) == 4 + 10
    # blessed too: blessed rnd(4) is drawn BEFORE silver rnd(20)
    assert (dmgval(obj("SILVER_DAGGER", blessed=True), vampire,
                   ScriptedRng(1, 3, 9)) == 2 + 4 + 10)
    # axe vs a wooden creature: rnd(6) base + rnd(4) axe
    wood_golem = FakeMon(replace(MONS[PM_STONE_GOLEM],
                                 pmidx=PM_NAMES.index("wood golem")))
    assert hates_silver(wood_golem.mdata) is False
    assert dmgval(obj("AXE"), wood_golem, ScriptedRng(3, 9)) == 4 + 2
    # goblin hates nothing: no bonus rolls, no dice after the base
    assert dmgval(obj("SILVER_DAGGER", blessed=True), goblin,
                  ScriptedRng(3)) == 4


def test_dmgval_heavy_iron_ball():
    assert dmgval(obj("HEAVY_IRON_BALL"), goblin, ScriptedRng(5)) == 6
    # 480 + 160: +rnd(4); presets 5, 2 -> 6 + 3
    assert (dmgval(obj("HEAVY_IRON_BALL", owt=640), goblin,
                   ScriptedRng(5, 2)) == 6 + 3)
    # 480 + 320: +rnd(8); presets 5, 2 -> 6 + 3 (2 % 8)
    assert (dmgval(obj("HEAVY_IRON_BALL", owt=800), goblin,
                   ScriptedRng(5, 2)) == 6 + 3)


def test_dmgval_erosion_floor():
    # rusted dagger: rnd(4) base - 3 erosion, floor 1
    assert dmgval(obj("DAGGER", oeroded=3), goblin, ScriptedRng(0)) == 1
    # greatest_erosion uses the larger of the two fields
    assert dmgval(obj("DAGGER", oeroded=1, oeroded2=3), goblin,
                  ScriptedRng(0)) == 1


# ------------------------------------------------------------
# abon / dbon
# ------------------------------------------------------------

def test_abon_table():
    # str on the 5.0 linear scale: 18/50 == 68, 18/100 == 118
    assert abon(5, 10, ulevel=5) == -2
    assert abon(7, 10, ulevel=5) == -1
    assert abon(16, 10, ulevel=5) == 0
    assert abon(17, 10, ulevel=5) == 1
    assert abon(67, 10, ulevel=5) == 1    # 18/49
    assert abon(68, 10, ulevel=5) == 2    # 18/50
    assert abon(117, 10, ulevel=5) == 2   # 18/99
    assert abon(118, 10, ulevel=5) == 3   # 18/100
    # low-level kludge (+1 below level 3) and the dex ladder
    assert abon(17, 3) == -1              # 1 + 1 - 3
    assert abon(17, 5) == 0               # 1 + 1 - 2
    assert abon(17, 7) == 1               # 1 + 1 - 1
    assert abon(17, 13) == 2              # 1 + 1
    assert abon(17, 15) == 3              # 1 + 1 + (15-14)
    assert abon(17, 10, ulevel=3) == 1    # no kludge at level 3
    # polymorphed: the monster's adjusted level minus 3
    assert abon(10, 10, upolyd=True, poly_lev=7) == 4


def test_dbon_table():
    assert dbon(5) == -1
    assert dbon(15) == 0
    assert dbon(17) == 1
    assert dbon(18) == 2      # 18/00
    assert dbon(93) == 3      # 18/75
    assert dbon(94) == 4      # 18/76
    assert dbon(108) == 4     # 18/90
    assert dbon(109) == 5     # 18/91
    assert dbon(117) == 5     # 18/99
    assert dbon(118) == 6     # 18/100
    assert dbon(5, upolyd=True) == 0


# ------------------------------------------------------------
# the skill system
# ------------------------------------------------------------

def test_skill_init_role_flow():
    s = Skills()
    table = (DefSkill(Skill.P_DAGGER, P_SKILLED),
             DefSkill(Skill.P_BOW, P_EXPERT),
             DefSkill(Skill.P_BARE_HANDED_COMBAT, P_SKILLED))
    skill_init(s, table, held=(int(O.DAGGER), int(O.ARROW)), role="")
    # carried dagger -> basic; carried arrows (ammo) -> no bow skill
    assert s.skill[Skill.P_DAGGER] == P_BASIC
    assert s.skill[Skill.P_BOW] == P_UNSKILLED
    assert s.max_skill[Skill.P_DAGGER] == P_SKILLED
    assert s.max_skill[Skill.P_BOW] == P_EXPERT
    # advance is seeded one step below the current level
    assert s.advance[Skill.P_DAGGER] == practice_needed_to_advance(P_BASIC - 1)
    assert s.advance[Skill.P_BOW] == 0
    # high-potential hands: max > expert starts basic
    assert s.skill[Skill.P_BARE_HANDED_COMBAT] == P_BASIC
    # the P_NONE slot is unrestrictable (C calls unrestrict_weapon_skill
    # with P_NONE via the special-spell default)
    assert s.skill[Skill.P_NONE] == P_UNSKILLED


def test_skill_init_role_magic():
    s = Skills()
    skill_init(s, (DefSkill(Skill.P_ATTACK_SPELL, P_EXPERT),),
              role="wizard")
    assert s.skill[Skill.P_ATTACK_SPELL] == P_BASIC
    assert s.skill[Skill.P_ENCHANTMENT_SPELL] == P_BASIC
    s2 = Skills()
    skill_init(s2, (DefSkill(Skill.P_HEALING_SPELL, P_EXPERT),),
              role="monk")
    assert s2.skill[Skill.P_HEALING_SPELL] == P_BASIC
    s3 = Skills()
    skill_init(s3, (DefSkill(Skill.P_CLERIC_SPELL, P_EXPERT),),
              role="cleric")
    assert s3.skill[Skill.P_CLERIC_SPELL] == P_BASIC


def test_use_skill_threshold_message():
    s = Skills()
    skill_init(s, (DefSkill(Skill.P_DAGGER, P_EXPERT),))
    assert s.skill[Skill.P_DAGGER] == P_UNSKILLED
    assert not can_advance(s, Skill.P_DAGGER)
    assert use_skill(s, Skill.P_DAGGER, 20) == \
        "You feel more confident in your weapon skills."
    assert can_advance(s, Skill.P_DAGGER)
    # below the threshold: no message
    s2 = Skills()
    skill_init(s2, (DefSkill(Skill.P_DAGGER, P_EXPERT),))
    assert use_skill(s2, Skill.P_DAGGER, 5) is None
    assert use_skill(s2, Skill.P_DAGGER, 15) is None
    assert can_advance(s2, Skill.P_DAGGER)


def test_slots_and_advance_cost():
    s = Skills()
    skill_init(s, (DefSkill(Skill.P_DAGGER, P_EXPERT),),
              held=(int(O.DAGGER),))
    assert s.skill[Skill.P_DAGGER] == P_BASIC
    assert s.weapon_slots == 1
    use_skill(s, Skill.P_DAGGER, 80)
    assert not can_advance(s, Skill.P_DAGGER)  # practiced, but 2 slots needed
    add_weapon_skill(s, 1)                     # a level-up slot
    assert can_advance(s, Skill.P_DAGGER)
    msg = advance_skill(s, Skill.P_DAGGER)
    assert s.skill[Skill.P_DAGGER] == P_SKILLED
    assert s.weapon_slots == 1 + 1 - 2
    assert msg == "You are now more skilled in dagger."
    assert s.skill_record == [Skill.P_DAGGER] and s.skills_advanced == 1
    # practice does not reset on advance; skilled->expert needs 180 and 3
    use_skill(s, Skill.P_DAGGER, 180)          # 100 + 180 = 280 >= 180
    add_weapon_skill(s, 2)                     # 1 + 2 = 3 slots
    assert can_advance(s, Skill.P_DAGGER)
    advance_skill(s, Skill.P_DAGGER)
    assert s.skill[Skill.P_DAGGER] == P_EXPERT
    assert s.weapon_slots == 0


def test_lose_weapon_skill():
    s = Skills()
    skill_init(s, (DefSkill(Skill.P_DAGGER, P_EXPERT),),
              held=(int(O.DAGGER),))
    s.weapon_slots = 5
    use_skill(s, Skill.P_DAGGER, 80)
    advance_skill(s, Skill.P_DAGGER)
    assert s.weapon_slots == 3
    lose_weapon_skill(s, 3)
    assert s.weapon_slots == 0 and s.skill[Skill.P_DAGGER] == P_SKILLED
    lose_weapon_skill(s, 1)
    assert s.skill[Skill.P_DAGGER] == P_BASIC
    assert s.weapon_slots == 1  # slots_required(basic) - 1 == 2 - 1
    assert s.skills_advanced == 0


def test_drain_weapon_skill():
    s = Skills()
    skill_init(s, (DefSkill(Skill.P_DAGGER, P_EXPERT),
                   DefSkill(Skill.P_BOW, P_EXPERT)),
              held=(int(O.DAGGER), int(O.BOW)))
    assert s.skill[Skill.P_DAGGER] == P_BASIC and s.skill[Skill.P_BOW] == P_BASIC
    s.weapon_slots = 4
    use_skill(s, Skill.P_DAGGER, 80); advance_skill(s, Skill.P_DAGGER)
    use_skill(s, Skill.P_BOW, 80);    advance_skill(s, Skill.P_BOW)
    # skill_record = [dagger, bow]; drain picks rn2(2) -> 1 = the bow
    msgs = drain_weapon_skill(s, 1, ScriptedRng(1, 30))
    assert s.skill[Skill.P_BOW] == P_BASIC and s.skill[Skill.P_DAGGER] == P_SKILLED
    assert msgs == ["You forget some of your training in bow."]
    assert s.skill_record == [Skill.P_DAGGER] and s.skills_advanced == 1
    # practice is rolled back into the new level's range: 20 + rn2(60)
    assert s.advance[Skill.P_BOW] == 20 + 30


def test_peaked_skill():
    s = Skills()
    skill_init(s, (DefSkill(Skill.P_DAGGER, P_BASIC),),
              held=(int(O.DAGGER),))
    assert not can_advance(s, Skill.P_DAGGER)
    assert not could_advance(s, Skill.P_DAGGER)
    assert not peaked_skill(s, Skill.P_DAGGER)  # no practice yet
    use_skill(s, Skill.P_DAGGER, 80)            # 20 + 80 >= 80
    assert peaked_skill(s, Skill.P_DAGGER)
    assert not can_advance(s, Skill.P_DAGGER)   # still capped at basic


# ------------------------------------------------------------
# skill-based attack bonuses
# ------------------------------------------------------------

def test_weapon_hit_bonus():
    s = Skills()
    d = obj("DAGGER")
    for level, want in ((P_UNSKILLED, -4), (P_BASIC, 0), (P_SKILLED, 2),
                        (P_EXPERT, 3)):
        s.skill[Skill.P_DAGGER] = level
        assert weapon_hit_bonus(s, d) == want, level
    # two-weapon: the LOWER of the two skills applies
    s.skill[Skill.P_TWO_WEAPON_COMBAT] = P_EXPERT
    s.skill[Skill.P_DAGGER] = P_BASIC
    assert weapon_hit_bonus(s, d, twoweap=True, in_hands=True) == -7
    s.skill[Skill.P_DAGGER] = P_EXPERT
    assert weapon_hit_bonus(s, d, twoweap=True, in_hands=True) == -3
    # not in hand: the ordinary weapon skill applies
    assert weapon_hit_bonus(s, d, twoweap=True, in_hands=False) == 3
    # bare hands: b.h. basic +1, skilled +2, expert +2, master +3
    for level, want in ((P_BASIC, 1), (P_SKILLED, 2), (P_EXPERT, 2),
                        (P_MASTER, 3)):
        s.skill[Skill.P_BARE_HANDED_COMBAT] = level
        assert weapon_hit_bonus(s, None) == want, level
    # mounted and unskilled in riding
    s.skill[Skill.P_RIDING] = P_UNSKILLED
    s.skill[Skill.P_DAGGER] = P_BASIC
    assert weapon_hit_bonus(s, d, mounted=True) == 0 - 2


def test_weapon_hit_bonus_martial():
    s = Skills()
    s.skill[Skill.P_BARE_HANDED_COMBAT] = P_SKILLED
    assert weapon_hit_bonus(s, None) == 2
    assert weapon_hit_bonus(s, None, martial=True) == 4


def test_weapon_dam_bonus():
    s = Skills()
    d = obj("DAGGER")
    for level, want in ((P_UNSKILLED, -2), (P_BASIC, 0), (P_SKILLED, 1),
                        (P_EXPERT, 2)):
        s.skill[Skill.P_DAGGER] = level
        assert weapon_dam_bonus(s, d) == want, level
    # bare hands, including the martial multiplier
    s.skill[Skill.P_BARE_HANDED_COMBAT] = P_SKILLED
    assert weapon_dam_bonus(s, None) == 1
    assert weapon_dam_bonus(s, None, martial=True) == 4
    s.skill[Skill.P_BARE_HANDED_COMBAT] = P_GRAND_MASTER
    assert weapon_dam_bonus(s, None, martial=True) == 9
    # two-weapon uses the lower skill
    s.skill[Skill.P_TWO_WEAPON_COMBAT] = P_EXPERT
    s.skill[Skill.P_DAGGER] = P_SKILLED
    assert weapon_dam_bonus(s, d, twoweap=True, in_hands=True) == 0
    # riding thrust: skilled +1, expert +2 (never for two-weapon)
    s.skill[Skill.P_RIDING] = P_SKILLED
    s.skill[Skill.P_DAGGER] = P_BASIC
    assert weapon_dam_bonus(s, d, mounted=True) == 1
    s.skill[Skill.P_RIDING] = P_EXPERT
    assert weapon_dam_bonus(s, d, mounted=True) == 2
    s.skill[Skill.P_DAGGER] = P_EXPERT
    assert weapon_dam_bonus(s, d, twoweap=True, in_hands=True,
                            mounted=True) == 1


# ------------------------------------------------------------
# data for the mon.c port
# ------------------------------------------------------------

def test_monster_weapon_tables():
    # every RWERP entry is a weapon, weptool, stone, or the cream pie
    from core.objects import ObjClass
    for otyp in RWERP:
        assert int(OBJECTS[otyp].oclass) in (
            int(ObjClass.WEAPON), int(ObjClass.TOOL), int(ObjClass.FOOD)), otyp
    # the throw-and-return table resolves
    from core.weapon import autoreturn_weapon
    assert autoreturn_weapon(obj("AKLYS")).tethered == 1
    assert autoreturn_weapon(obj("BOOMERANG")) is None
    from core.weapon import monmightthrowwep
    assert monmightthrowwep(obj("DAGGER"))
    assert not monmightthrowwep(obj("BULLWHIP"))


def test_stubs_raise():
    from core.weapon import (enhance_weapon_skill, mon_wield_item,
                             possibly_unwield, select_hwep, select_rwep,
                             silver_sears, show_skills, special_dmgval)
    for fn in (enhance_weapon_skill, show_skills, select_hwep):
        try:
            fn() if fn not in (select_hwep,) else fn(None)
            raise AssertionError(f"{fn.__name__} did not raise")
        except NotImplementedError:
            pass
    for fn in (select_rwep, possibly_unwield, mon_wield_item, special_dmgval,
               silver_sears):
        try:
            fn(None, None, None, None)
            raise AssertionError(f"{fn.__name__} did not raise")
        except NotImplementedError:
            pass
