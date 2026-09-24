"""Tests for the object type table (core.objects).

The table is a mechanical transcription of include/objects.h; these
tests pin the C numbering (so any future reordering fails loudly),
the macro expansions for representative rows, and the class ranges.
"""
from core.objects import (ObjClass, ObjType, OBJECTS, BASES, NUM_OBJECTS,
                          FIRST_OBJECT, FIRST_AMULET, LAST_AMULET,
                          FIRST_SPELL, LAST_SPELL, FIRST_REAL_GEM,
                          LAST_REAL_GEM, FIRST_GLASS_GEM, LAST_GLASS_GEM,
                          MAXOCLASSES, O)


def test_table_length():
    assert len(OBJECTS) == NUM_OBJECTS
    # NetHack 5.0 ships 480 object types
    assert NUM_OBJECTS == 480


def test_c_numbering():
    assert O.STRANGE_OBJECT == 0
    assert O.GENERIC_VENOM == 17
    assert O.ARROW == 18
    assert O.CROSSBOW == 88
    assert O.ELVEN_LEATHER_HELM == 89
    assert O.LEVITATION_BOOTS == 172
    assert O.RIN_ADORNMENT == 173
    assert O.RIN_PROTECTION_FROM_SHAPE_CHAN == 200
    assert O.AMULET_OF_ESP == FIRST_AMULET == 201
    assert O.AMULET_OF_YENDOR == LAST_AMULET == 213
    assert O.LARGE_BOX == 214
    assert O.BELL_OF_OPENING == 263
    assert O.TRIPE_RATION == 264
    assert O.TIN == 296
    assert O.POT_WATER == 322
    assert O.SCR_BLANK_PAPER == 364
    assert O.SPE_DIG == FIRST_SPELL == 365
    assert O.SPE_CHAIN_LIGHTNING == 405
    assert O.SPE_BLANK_PAPER == LAST_SPELL == 406
    assert O.SPE_BOOK_OF_THE_DEAD == 408
    assert O.WAN_LIGHT == 409
    assert O.WAN3 == 436
    assert O.GOLD_PIECE == 437
    assert O.DILITHIUM_CRYSTAL == FIRST_REAL_GEM == 438
    assert O.JADE == LAST_REAL_GEM == 459
    assert O.WORTHLESS_WHITE_GLASS == FIRST_GLASS_GEM == 460
    assert O.WORTHLESS_VIOLET_GLASS == LAST_GLASS_GEM == 468
    assert O.ROCK == 473
    assert O.BOULDER == 474
    assert O.ACID_VENOM == NUM_OBJECTS - 1 == 479


def test_class_bases():
    assert BASES[ObjClass.ILLOBJ] == 0
    assert BASES[ObjClass.WEAPON] == O.ARROW
    assert BASES[ObjClass.ARMOR] == O.ELVEN_LEATHER_HELM
    assert BASES[ObjClass.RING] == O.RIN_ADORNMENT
    assert BASES[ObjClass.AMULET] == O.AMULET_OF_ESP
    assert BASES[ObjClass.TOOL] == O.LARGE_BOX
    assert BASES[ObjClass.FOOD] == O.TRIPE_RATION
    assert BASES[ObjClass.POTION] == O.POT_GAIN_ABILITY
    assert BASES[ObjClass.SCROLL] == O.SCR_ENCHANT_ARMOR
    assert BASES[ObjClass.SPBOOK] == O.SPE_DIG
    assert BASES[ObjClass.WAND] == O.WAN_LIGHT
    assert BASES[ObjClass.COIN] == O.GOLD_PIECE
    assert BASES[ObjClass.GEM] == O.DILITHIUM_CRYSTAL
    assert BASES[ObjClass.ROCK] == O.BOULDER
    assert BASES[ObjClass.VENOM] == O.BLINDING_VENOM
    assert BASES[MAXOCLASSES] == NUM_OBJECTS


def test_generic_slots():
    for i in range(1, MAXOCLASSES):
        assert OBJECTS[i].oclass == i
        assert OBJECTS[i].unique
        assert OBJECTS[i].prob == 0
        assert OBJECTS[i].name == f"generic {OBJECTS[i].descr}"


def test_weapon_rows():
    arrow = OBJECTS[O.ARROW]
    assert arrow.oclass == ObjClass.WEAPON
    assert arrow.subtyp == -20          # -P_BOW
    assert arrow.oc1 == 0               # no hit bonus
    assert arrow.wsdam == 6 and arrow.wldam == 6
    assert arrow.merge and arrow.uses_known and arrow.charged
    assert arrow.material == 11         # IRON
    assert arrow.nutrition == arrow.weight == 1
    # ammo/launcher pairing
    assert OBJECTS[O.ARROW].subtyp == -OBJECTS[O.BOW].subtyp
    assert OBJECTS[O.CROSSBOW_BOLT].subtyp == -OBJECTS[O.CROSSBOW].subtyp
    assert OBJECTS[O.DART].subtyp == -23      # -P_DART
    assert OBJECTS[O.SHURIKEN].subtyp == -24  # -P_SHURIKEN
    # bow: sdam=ldam=2, no hit bonus, mergeable bit is 0
    bow = OBJECTS[O.BOW]
    assert bow.wsdam == 2 and bow.wldam == 2
    assert not bow.merge
    assert OBJECTS[O.SLING].subtyp == 21
    assert OBJECTS[O.KATANA].oc1 == 1
    assert OBJECTS[O.TWO_HANDED_SWORD].big
    assert OBJECTS[O.DWARVISH_MATTOCK].oc1 == -1


def test_armor_rows():
    plate = OBJECTS[O.PLATE_MAIL]
    assert plate.armor_ac == 7          # 10 - ac(3)
    assert plate.oc2 == 2               # a_can
    assert plate.subtyp == 0            # ARM_SUIT
    assert plate.big
    helm = OBJECTS[O.ELVEN_LEATHER_HELM]
    assert helm.subtyp == 2             # ARM_HELM
    assert helm.armor_ac == 1           # 10 - 9
    shield = OBJECTS[O.SMALL_SHIELD]
    assert shield.subtyp == 1           # ARM_SHIELD
    cloak = OBJECTS[O.CLOAK_OF_PROTECTION]
    assert cloak.subtyp == 5            # ARM_CLOAK
    assert cloak.oprop == 59            # PROTECTION
    boots = OBJECTS[O.SPEED_BOOTS]
    assert boots.subtyp == 4            # ARM_BOOTS
    assert boots.oprop == 64            # FAST
    gloves = OBJECTS[O.GAUNTLETS_OF_POWER]
    assert gloves.subtyp == 3           # ARM_GLOVES
    # dragon gear order matches the dragons (mail 101..110, scales 111..120)
    assert O.GRAY_DRAGON_SCALE_MAIL == 101
    assert O.YELLOW_DRAGON_SCALE_MAIL == 110
    assert O.GRAY_DRAGON_SCALES == 111
    assert O.YELLOW_DRAGON_SCALES == 120
    assert OBJECTS[O.RED_DRAGON_SCALE_MAIL].oprop == 1  # FIRE_RES


def test_ring_rows():
    ring = OBJECTS[O.RIN_PROTECTION]
    assert ring.oprop == 59             # PROTECTION
    assert ring.weight == 3 and ring.nutrition == 15
    assert ring.uses_known and ring.charged
    assert OBJECTS[O.RIN_ADORNMENT].oprop == 39       # ADORNED
    assert not OBJECTS[O.RIN_ADORNMENT].tough         # mohs 2 < 8
    assert OBJECTS[O.RIN_WARNING].tough               # diamond, mohs 10


def test_amulet_rows():
    amulet = OBJECTS[O.AMULET_OF_YENDOR]
    assert amulet.unique and amulet.nowish and amulet.magic
    assert amulet.cost == 30000
    fake = OBJECTS[O.FAKE_AMULET_OF_YENDOR]
    assert not fake.magic and not fake.unique
    assert fake.descr == "Amulet of Yendor"
    assert OBJECTS[O.AMULET_OF_FLYING].oprop == 49    # FLYING


def test_tool_rows():
    assert OBJECTS[O.LARGE_BOX].oclass == ObjClass.TOOL
    assert OBJECTS[O.BAG_OF_HOLDING].magic
    assert OBJECTS[O.TIN_OPENER].weight == 4
    assert OBJECTS[O.UNICORN_HORN].oc1 == 1           # PIERCE strike
    assert OBJECTS[O.UNICORN_HORN].subtyp == 27       # P_UNICORN_HORN
    assert OBJECTS[O.CANDELABRUM_OF_INVOCATION].unique
    assert OBJECTS[O.BELL_OF_OPENING].charged


def test_food_rows():
    assert OBJECTS[O.TRIPE_RATION].nutrition == 200
    assert OBJECTS[O.TRIPE_RATION].delay == 2
    assert OBJECTS[O.LEMBAS_WAFER].nutrition == 800
    assert OBJECTS[O.CORPSE].prob == 0
    assert OBJECTS[O.EGG].uses_known
    assert not OBJECTS[O.MEAT_RING].merge
    assert OBJECTS[O.FOOD_RATION].cost == 45          # 800/20 + 5
    assert OBJECTS[O.TIN].prob == 75


def test_potion_rows():
    assert OBJECTS[O.POT_HEALING].prob == 115
    assert OBJECTS[O.POT_HEALING].descr == "purple-red"
    assert not OBJECTS[O.POT_WATER].magic
    assert OBJECTS[O.POT_CONFUSION].oprop == 14       # CONFUSION
    assert OBJECTS[O.POT_SPEED].oprop == 64           # FAST
    assert OBJECTS[O.POT_LEVITATION].weight == 20
    assert OBJECTS[O.POT_LEVITATION].nutrition == 10


def test_scroll_rows():
    assert OBJECTS[O.SCR_IDENTIFY].prob == 180
    assert OBJECTS[O.SCR_STINKING_CLOUD].descr == "VELOX NEB"
    assert OBJECTS[O.SC10].descr == "ASHPD SODALG"
    assert OBJECTS[O.SC10].name is None
    assert not OBJECTS[O.SCR_BLANK_PAPER].magic
    assert OBJECTS[O.SCR_BLANK_PAPER].prob == 28


def test_spellbook_rows():
    dig = OBJECTS[O.SPE_DIG]
    assert dig.spell_level == 5
    assert dig.material == 7          # LEATHER pages
    assert dig.cost == 500            # level * 100
    fod = OBJECTS[O.SPE_FINGER_OF_DEATH]
    assert fod.spell_level == 7
    assert OBJECTS[O.SPE_BLANK_PAPER].subtyp == 0
    assert not OBJECTS[O.SPE_BLANK_PAPER].magic
    assert OBJECTS[O.SPE_NOVEL].uses_known
    dead = OBJECTS[O.SPE_BOOK_OF_THE_DEAD]
    assert dead.unique and dead.nowish
    assert dead.spell_level == 7
    assert dead.cost == 10000


def test_wand_rows():
    assert OBJECTS[O.WAN_LIGHT].dir == 1      # NODIR
    assert OBJECTS[O.WAN_DIGGING].dir == 3    # RAY
    assert OBJECTS[O.WAN_STRIKING].dir == 2   # IMMEDIATE
    assert OBJECTS[O.WAN_WISHING].prob == 5
    assert OBJECTS[O.WAN1].name is None
    assert OBJECTS[O.WAN1].descr == "forked"
    assert OBJECTS[O.WAN_NOTHING].magic is False


def test_coin_gem_rows():
    coin = OBJECTS[O.GOLD_PIECE]
    assert coin.prob == 1000 and coin.cost == 1
    assert coin.weight == 1
    dia = OBJECTS[O.DIAMOND]
    assert dia.cost == 4000 and dia.tough
    assert dia.subtyp == -21             # -P_SLING
    glass = OBJECTS[O.WORTHLESS_BLUE_GLASS]
    assert not glass.tough
    assert glass.material == 19          # GLASS
    assert not glass.tough
    rock = OBJECTS[O.ROCK]
    assert rock.name_known and rock.prob == 100
    assert rock.wsdam == 3 and rock.wldam == 3
    assert not rock.magic
    luck = OBJECTS[O.LUCKSTONE]
    assert luck.magic


def test_misc_rows():
    boulder = OBJECTS[O.BOULDER]
    assert boulder.big and boulder.weight == 6000
    assert boulder.wsdam == 20 and boulder.nutrition == 2000
    assert OBJECTS[O.STATUE].oclass == ObjClass.ROCK
    ball = OBJECTS[O.HEAVY_IRON_BALL]
    assert ball.dir == 4                  # WHACK
    assert ball.oclass == ObjClass.BALL
    venom = OBJECTS[O.ACID_VENOM]
    assert venom.oclass == ObjClass.VENOM
    assert venom.wsdam == 6 and venom.nowish
