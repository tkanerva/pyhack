"""Tests for the monster type table (core.monst)."""
from core import monst
from core.monst import (MONS, PM_NAMES, NUMMONS, SPECIAL_PM, SUBSET_PM,
                        Attack, defch, is_dragon, is_golem, monclass,
                        monname, monsndx)
import core.monst as M


def test_table_shape():
    assert len(MONS) == NUMMONS == 383
    assert len(PM_NAMES) == NUMMONS
    assert len(SUBSET_PM) == 40
    assert sum(1 for m in MONS if m is not None) == 40


def test_pm_names_anchors():
    # spot-checks against include/monsters.h ordering (default build:
    # CHARON undefined; MAIL_STRUCTURES always defined in 5.0)
    assert PM_NAMES[0] == "giant ant"
    assert PM_NAMES[10] == "cockatrice"
    assert PM_NAMES[70] == "goblin"
    assert PM_NAMES[126] == "bat"
    assert PM_NAMES[143] == "gray dragon"
    assert PM_NAMES[152] == "yellow dragon"
    assert PM_NAMES[248] == "skeleton"
    assert PM_NAMES[287] == "ghost"
    assert PM_NAMES[314] == "mail daemon"  # MAIL_STRUCTURES in 5.0
    assert PM_NAMES[315] == "djinni"
    assert PM_NAMES[330] == "long worm tail"
    assert PM_NAMES[382] == "apprentice"


def test_special_pm_anchor():
    assert SPECIAL_PM == M.PM_LONG_WORM_TAIL
    assert MONS[SPECIAL_PM].mlet == M.S_WORM_TAIL
    # the special section is G_NOGEN and M2_NOPOLY (C optimization)
    for i in range(SPECIAL_PM, NUMMONS):
        m = MONS[i]
        if m is not None:
            assert m.geno & M.G_NOGEN
            assert m.mflags2 & M.M2_NOPOLY


def test_dragon_range():
    # defended() in mondata.c uses this exact range
    assert M.PM_GRAY_DRAGON < M.PM_BLACK_DRAGON <= M.PM_YELLOW_DRAGON
    assert M.PM_YELLOW_DRAGON - M.PM_GRAY_DRAGON + 1 == 10
    for i in range(M.PM_GRAY_DRAGON, M.PM_YELLOW_DRAGON + 1):
        assert is_dragon(MONS[i]) or MONS[i] is None


def test_monsndx_and_monclass():
    g = MONS[M.PM_GOBLIN]
    assert monsndx(g) == M.PM_GOBLIN
    assert monclass(g) == M.S_ORC
    assert defch(monclass(g)) == "o"
    assert defch(M.S_BAT) == "B"
    assert defch(M.S_GHOST) == " "
    assert defch(M.S_HUMAN) == "@"


def test_monname():
    assert monname(MONS[M.PM_TROLL]) == "troll"
    assert monname(MONS[M.PM_VAMPIRE], M.NEUTRAL) == "vampire"


def test_goblin_fields():
    g = MONS[M.PM_GOBLIN]
    assert (g.mlevel, g.mmove, g.ac, g.mr, g.maligntyp) == (0, 6, 10, 0, -3)
    assert g.geno == (M.G_GENO | 2)
    assert g.mattk[0] == Attack(M.AT_WEAP, M.AD_PHYS, 1, 4)
    assert all(a == M.NO_ATK for a in g.mattk[1:])
    assert (g.cwt, g.cnutrit, g.msound, g.msize) == (400, 100, M.MS_ORC, M.MZ_SMALL)
    assert g.mresists == 0 and g.mconveys == 0
    assert g.mflags1 == (M.M1_HUMANOID | M.M1_OMNIVORE)
    assert g.mflags2 == (M.M2_ORC | M.M2_COLLECT)
    assert g.mflags3 == (M.M3_INFRAVISIBLE | M.M3_INFRAVISION)
    assert (g.difficulty, g.mcolor) == (1, 7)


def test_cockatrice_petriphy_attacks():
    c = MONS[M.PM_COCKATRICE]
    assert c.mattk[0] == Attack(M.AT_BITE, M.AD_PHYS, 1, 3)
    assert c.mattk[1] == Attack(M.AT_TUCH, M.AD_STON, 0, 0)
    assert c.mattk[2] == Attack(M.AT_NONE, M.AD_STON, 0, 0)
    assert c.mresists == (M.MR_POISON | M.MR_STONE)
    assert c.mconveys == (M.MR_POISON | M.MR_STONE)


def test_bat_is_fast():
    b = MONS[M.PM_BAT]
    assert b.mmove == 22
    assert b.mflags2 & M.M2_WANDER
    assert not (b.mflags2 & M.M2_HOSTILE)  # bats start non-hostile


def test_black_disintegration_breath():
    d = MONS[M.PM_BLACK_DRAGON]
    assert d.mattk[0] == Attack(M.AT_BREA, M.AD_DISN, 1, 255)
    assert d.mresists == M.MR_DISINT
    assert d.mconveys == M.MR_DISINT


def test_vampire_drains_life():
    v = MONS[M.PM_VAMPIRE]
    assert v.mattk[1] == Attack(M.AT_BITE, M.AD_DRLI, 1, 6)
    assert v.mflags2 & (M.M2_UNDEAD | M.M2_SHAPESHIFTER)
    assert v.geno & M.G_NOCORPSE


def test_skeleton_is_nogen_and_uses_a_weapon():
    s = MONS[M.PM_SKELETON]
    assert s.geno == (M.G_NOCORPSE | M.G_NOGEN)
    assert s.mattk[0] == Attack(M.AT_WEAP, M.AD_PHYS, 2, 6)
    assert s.mattk[1] == Attack(M.AT_TUCH, M.AD_SLOW, 1, 6)
    assert s.msound == M.MS_BONES


def test_flesh_golem_geno_is_bare_frequency():
    # C: (1) -- frequency 1, no G_GENO (not genocidable)
    f = MONS[M.PM_FLESH_GOLEM]
    assert f.geno == 1
    assert not (f.geno & M.G_GENO)
    assert is_golem(f)


def test_troll_regenerates():
    t = MONS[M.PM_TROLL]
    assert t.mflags1 & M.M1_REGEN
    assert t.mattk[0] == Attack(M.AT_WEAP, M.AD_PHYS, 4, 2)


def test_fire_elemental():
    e = MONS[M.PM_FIRE_ELEMENTAL]
    assert e.mattk[0] == Attack(M.AT_CLAW, M.AD_FIRE, 3, 6)
    assert e.mattk[1] == Attack(M.AT_NONE, M.AD_FIRE, 0, 4)
    assert e.mresists == (M.MR_FIRE | M.MR_POISON | M.MR_STONE)
    assert e.mflags1 & (M.M1_UNSOLID | M.M1_FLY | M.M1_BREATHLESS)
    assert e.cwt == 0  # ethereal


def test_ghost_is_unsolid_and_wallwalking():
    g = MONS[M.PM_GHOST]
    assert g.geno == (M.G_NOCORPSE | M.G_NOGEN)
    assert g.mflags1 & (M.M1_WALLWALK | M.M1_UNSOLID | M.M1_FLY)
    assert g.mflags3 & M.M3_INFRAVISION


def test_worm_tail_is_inert():
    w = MONS[M.PM_LONG_WORM_TAIL]
    assert all(a == M.NO_ATK for a in w.mattk)
    assert w.mlevel == 0 and w.mmove == 0
    assert w.geno & (M.G_NOGEN | M.G_UNIQ)


def test_noattacks_flag_consistency():
    # every implemented monster has at least the right number of
    # attack slots, and aatyp 0 means "no attack" in that slot
    for idx in SUBSET_PM:
        m = MONS[idx]
        assert len(m.mattk) == M.NATTK
        for a in m.mattk:
            assert 0 <= a.aatyp <= 255
            assert 0 <= a.adtyp <= 253
        if m.mlet == M.S_WORM_TAIL:
            continue
        assert any(a.aatyp for a in m.mattk)


def test_distance_attack_classification():
    d = MONS[M.PM_BLACK_DRAGON]
    assert M.distance_atk_type(d.mattk[0].aatyp)   # breath
    g = MONS[M.PM_GOBLIN]
    assert not M.distance_atk_type(g.mattk[0].aatyp)  # weapon
