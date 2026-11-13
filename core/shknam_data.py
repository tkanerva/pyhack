"""The shop-type table (shtypes[]) and the shopkeeper name lists.

Data only, no behaviour: port of the two tables src/shknam.c declares
above its functions -- the ``shtypes[]`` array (shknam.c 209-357) and
the twelve ``shk*`` name arrays (shknam.c 39-207).  The functions that
read them live in core.shk.

C provenance:

  src/shknam.c  the name arrays (shkgeneral .. shkhealthfoods) and
                ``const struct shclass shtypes[]``
  include/mkroom.h  ``struct shclass`` (name, annotation, symb, prob,
                shdist, iprobs[9], shknms) and the D_* placement codes

Table policy (the ``*_data.py`` convention, core.monst_data /
core.objects_data): transcribed verbatim, in C order, so the shop
index ``i`` means what it means in C -- ``SHOPBASE + i`` is the room
type (core.types.RoomType) and ``shtypes[i]`` the class row.  The one
sentinel row (``{ (char *) 0, ... }``) is omitted: a Python list needs
no terminator, and ``SHOPNAMES`` (C's "the names are unique, are not
shared with any other shopkeeper" half) is the name list each row
points at.

Everything about a row is C's:

- ``prob`` is the shop-type probability out of 100.  The one
  "unique" shop (the lighting store, the last row) has probability 0
  by design: it is only created by the special-level loader
  (PLAN-SPLEV.md).  (PLAN-SPECIAL-ROOMS.md §6 says "the four
  zero-probability special-level shops"; this NetHack's table has
  exactly one, and the sentinel row is not a shop.)
- ``symb`` is the shop's object class -- ``ObjClass.RANDOM`` for the
  general store (C: RANDOM_CLASS), which sells anything.
- ``shdist`` is the object-placement type.  C defines D_SCATTER /
  D_SHOP / D_TEMPLE and says "not yet used but might be someday"; the
  stocking code only ever implements D_SHOP, so the field is carried
  for the table's sake.
- ``iprobs`` is the nine-slot ``struct itp`` array: the object
  classes the shop stocks, each with its probability out of 100.  A
  negative ``itype`` is a *specific* object type (C prepends the unary
  minus so the code can tell ``mkobj()`` from ``mksobj()``);
  ``VEGETARIAN_CLASS`` is the health-food store's pseudo-class (C:
  ``MAXOCLASSES + 1``, a class that does not exist in objects[]).

The name lists start with a prefix character that encodes gender (C's
"Name prefix codes" comment, shknam.c 20-30):

    dash  -  female, personal name
    underscore _  female, general name
    plus  +  male, personal name
    vertical bar |  male, general name (implied for most of shktools)
    equals =  gender not specified, personal name

Personal names do not receive the honorific prefix "Mr." / "Ms." --
that half is ``shkname()`` (core.shk, phase 4d).

Adaptations (documented, not bugs):

- the ``#ifdef OVERLAY / WIN32 / MAC68K / AMIGA / TOS / OS2 / VMS``
  tail of ``shktools`` belongs to those platform builds; this is the
  plain build, so the list is the unconditional forty names.
- ``init_shop_selection()`` (the probability validator) is inside
  ``#if 0`` in C as well: C does not compile it either.  The totals
  are checked by tests/test_shop.py instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .objects_defs import MAXOCLASSES, ObjClass
from .objects_enum import O

# C: shknam.c -- `#define VEGETARIAN_CLASS (MAXOCLASSES + 1)`: the
# health-food store's pseudo object class (it is not an objects[]
# class; shkveg() rolls a vegetarian FOOD_CLASS row for it).
VEGETARIAN_CLASS = MAXOCLASSES + 1

# C: include/mkroom.h -- the object placement types of struct shclass.
# Only D_SHOP is ever implemented (every row below is D_SHOP).
D_SCATTER = 0  # normal placement
D_SHOP = 1  # shop-like placement
D_TEMPLE = 2  # temple-like placement


@dataclass(frozen=True)
class ShopType:
    """One ``shtypes[]`` row (C: struct shclass, mkroom.h).

    ``iprobs`` is the nine-slot ``struct itp`` array: (iprob, itype)
    pairs, ``itype`` negative for a specific object type, or the
    pseudo-class ``VEGETARIAN_CLASS``.
    """

    name: str  # the shop type's name ("general store")
    name2: str  # the shorter #overview annotation; "" where C has NULL
    symb: int  # the object class it sells (ObjClass value)
    prob: int  # the shop-type probability out of 100
    shdist: int  # D_* placement type (unused, as in C)
    iprobs: Tuple[Tuple[int, int], ...]  # the nine struct itp slots
    shknms: Tuple[str, ...]  # the shopkeeper names, C order


# ------------------------------------------------------------
# The shopkeeper name lists (C: shknam.c 39-207)
# ------------------------------------------------------------

# Ukraine / Belarus / N. Russia / Silezie / Schweiz
SHKLIQUORS: Tuple[str, ...] = (
    "Njezjin", "Tsjernigof", "Ossipewsk", "Gorlowka",
    "Gomel",
    "Konosja", "Weliki Oestjoeg", "Syktywkar", "Sablja", "Narodnaja", "Kyzyl",
    "Walbrzych", "Swidnica", "Klodzko", "Raciborz", "Gliwice", "Brzeg",
    "Krnov", "Hradec Kralove",
    "Leuk", "Brig", "Brienz", "Thun", "Sarnen", "Burglen", "Elm", "Flims",
    "Vals", "Schuls", "Zum Loch",
)

# Eire
SHKBOOKS: Tuple[str, ...] = (
    "Skibbereen", "Kanturk", "Rath Luirc", "Ennistymon",
    "Lahinch", "Kinnegad", "Lugnaquillia", "Enniscorthy",
    "Gweebarra", "Kittamagh", "Nenagh", "Sneem",
    "Ballingeary", "Kilgarvan", "Cahersiveen", "Glenbeigh",
    "Kilmihil", "Kiltamagh", "Droichead Atha", "Inniscrone",
    "Clonegal", "Lisnaskea", "Culdaff", "Dunfanaghy",
    "Inishbofin", "Kesh",
)

# Turquie
SHKARMORS: Tuple[str, ...] = (
    "Demirci", "Kalecik", "Boyabai", "Yildizeli", "Gaziantep",
    "Siirt", "Akhalataki", "Tirebolu", "Aksaray", "Ermenak",
    "Iskenderun", "Kadirli", "Siverek", "Pervari", "Malasgirt",
    "Bayburt", "Ayancik", "Zonguldak", "Balya", "Tefenni",
    "Artvin", "Kars", "Makharadze", "Malazgirt", "Midyat",
    "Birecik", "Kirikkale", "Alaca", "Polatli", "Nallihan",
)

# Wales / Scotland
SHKWANDS: Tuple[str, ...] = (
    "Yr Wyddgrug", "Trallwng", "Mallwyd", "Pontarfynach", "Rhaeader",
    "Llandrindod", "Llanfair-ym-muallt", "Y-Fenni", "Maesteg", "Rhydaman",
    "Beddgelert", "Curig", "Llanrwst", "Llanerchymedd", "Caergybi",
    "Nairn", "Turriff", "Inverurie", "Braemar", "Lochnagar", "Kerloch",
    "Beinn a Ghlo", "Drumnadrochit", "Morven", "Uist", "Storr",
    "Sgurr na Ciche", "Cannich", "Gairloch", "Kyleakin", "Dunvegan",
)

# Hollandse familienamen / Skandinaviske navne
SHKRINGS: Tuple[str, ...] = (
    "Feyfer", "Flugi", "Gheel", "Havic", "Haynin",
    "Hoboken", "Imbyze", "Juyn", "Kinsky", "Massis",
    "Matray", "Moy", "Olycan", "Sadelin", "Svaving",
    "Tapper", "Terwen", "Wirix", "Ypey",
    "Rastegaisa", "Varjag Njarga", "Kautekeino", "Abisko", "Enontekis",
    "Rovaniemi", "Avasaksa", "Haparanda", "Lulea", "Gellivare",
    "Oeloe", "Kajaani", "Fauske",
)

# Indonesia
SHKFOODS: Tuple[str, ...] = (
    "Djasinga", "Tjibarusa", "Tjiwidej", "Pengalengan",
    "Bandjar", "Parbalingga", "Bojolali", "Sarangan",
    "Ngebel", "Djombang", "Ardjawinangun", "Berbek",
    "Papar", "Baliga", "Tjisolok", "Siboga",
    "Banjoewangi", "Trenggalek", "Karangkobar", "Njalindoeng",
    "Pasawahan", "Pameunpeuk", "Patjitan", "Kediri",
    "Pemboeang", "Tringanoe", "Makin", "Tipor",
    "Semai", "Berhala", "Tegal", "Samoe",
)

# Perigord
SHKWEAPONS: Tuple[str, ...] = (
    "Voulgezac", "Rouffiac", "Lerignac", "Touverac", "Guizengeard",
    "Melac", "Neuvicq", "Vanzac", "Picq", "Urignac",
    "Corignac", "Fleac", "Lonzac", "Vergt", "Queyssac",
    "Liorac", "Echourgnac", "Cazelon", "Eypau", "Carignan",
    "Monbazillac", "Jonzac", "Pons", "Jumilhac", "Fenouilledes",
    "Laguiolet", "Saujon", "Eymoutiers", "Eygurande", "Eauze",
    "Labouheyre",
)

# Spmi (the plain build: the #ifdef OVERLAY / WIN32 / ... tail is not
# in this list -- see the module docstring)
SHKTOOLS: Tuple[str, ...] = (
    "Ymla", "Eed-morra", "Elan Lapinski", "Cubask", "Nieb", "Bnowr Falr",
    "Sperc", "Noskcirdneh", "Yawolloh", "Hyeghu", "Niskal", "Trahnil",
    "Htargcm", "Enrobwem", "Kachzi Rellim", "Regien", "Donmyar", "Yelpur",
    "Nosnehpets", "Stewe", "Renrut", "Senna Hut", "-Zlaw", "Nosalnef",
    "Rewuorb", "Rellenk", "Yad", "Cire Htims", "Y-crad", "Nenilukah",
    "Corsh", "Aned", "Dark Eery", "Niknar", "Lapu", "Lechaim",
    "Rebrol-nek", "AlliWar Wickson", "Oguhmk", "Telloc Cyaj",
)

# Romania / Bulgaria
SHKLIGHT: Tuple[str, ...] = (
    "Zarnesti", "Slanic", "Nehoiasu", "Ludus", "Sighisoara", "Nisipitu",
    "Razboieni", "Bicaz", "Dorohoi", "Vaslui", "Fetesti", "Tirgu Neamt",
    "Babadag", "Zimnicea", "Zlatna", "Jiu", "Eforie", "Mamaia",
    "Silistra", "Tulovo", "Panagyuritshte", "Smolyan", "Kirklareli", "Pernik",
    "Lom", "Haskovo", "Dobrinishte", "Varvara", "Oryahovo", "Troyan",
    "Lovech", "Sliven",
)

# Suriname / Greenland / N. Canada / Iceland
SHKGENERAL: Tuple[str, ...] = (
    "Hebiwerie", "Possogroenoe", "Asidonhopo", "Manlobbi",
    "Adjama", "Pakka Pakka", "Kabalebo", "Wonotobo",
    "Akalapi", "Sipaliwini",
    "Annootok", "Upernavik", "Angmagssalik",
    "Aklavik", "Inuvik", "Tuktoyaktuk", "Chicoutimi",
    "Ouiatchouane", "Chibougamau", "Matagami", "Kipawa",
    "Kinojevis", "Abitibi", "Maganasipi",
    "Akureyri", "Kopasker", "Budereyri", "Akranes",
    "Bordeyri", "Holmavik",
)

# Tibet / Hippie names
SHKHEALTHFOODS: Tuple[str, ...] = (
    "Ga'er", "Zhangmu", "Rikaze", "Jiangji", "Changdu",
    "Linzhi", "Shigatse", "Gyantse", "Ganden", "Tsurphu",
    "Lhasa", "Tsedong", "Drepung",
    "=Azura", "=Blaze", "=Breanna", "=Breezy", "=Dharma",
    "=Feather", "=Jasmine", "=Luna", "=Melody", "=Moonjava",
    "=Petal", "=Rhiannon", "=Starla", "=Tranquilla", "=Windsong",
    "=Zennia", "=Zoe", "=Zora",
)


# ------------------------------------------------------------
# shtypes[] -- the shop classes (C: shknam.c 209-357)
# ------------------------------------------------------------
#
# The index into this tuple is the shop index: the room type is
# SHOPBASE + i (core.types.RoomType), and `shtypes[i]` is the class
# row the stocking code reads.  The four rows with prob == 0 are the
# "unique" shops -- special-level only, never rolled by mkshop().

SHOPTYPES: Tuple[ShopType, ...] = (
    ShopType(
        name="general store",
        name2="",
        symb=ObjClass.RANDOM,
        prob=42,
        shdist=D_SHOP,
        iprobs=((100, int(ObjClass.RANDOM)),) + ((0, 0),) * 8,
        shknms=SHKGENERAL,
    ),
    ShopType(
        name="used armor dealership",
        name2="armor shop",
        symb=ObjClass.ARMOR,
        prob=14,
        shdist=D_SHOP,
        iprobs=((90, int(ObjClass.ARMOR)), (10, int(ObjClass.WEAPON)))
        + ((0, 0),) * 7,
        shknms=SHKARMORS,
    ),
    ShopType(
        name="second-hand bookstore",
        name2="scroll shop",
        symb=ObjClass.SCROLL,
        prob=10,
        shdist=D_SHOP,
        iprobs=((90, int(ObjClass.SCROLL)), (10, int(ObjClass.SPBOOK)))
        + ((0, 0),) * 7,
        shknms=SHKBOOKS,
    ),
    ShopType(
        name="liquor emporium",
        name2="potion shop",
        symb=ObjClass.POTION,
        prob=10,
        shdist=D_SHOP,
        iprobs=((100, int(ObjClass.POTION)),) + ((0, 0),) * 8,
        shknms=SHKLIQUORS,
    ),
    ShopType(
        name="antique weapons outlet",
        name2="weapon shop",
        symb=ObjClass.WEAPON,
        prob=5,
        shdist=D_SHOP,
        iprobs=((90, int(ObjClass.WEAPON)), (10, int(ObjClass.ARMOR)))
        + ((0, 0),) * 7,
        shknms=SHKWEAPONS,
    ),
    ShopType(
        name="delicatessen",
        name2="food shop",
        symb=ObjClass.FOOD,
        prob=5,
        shdist=D_SHOP,
        iprobs=(
            (83, int(ObjClass.FOOD)),
            (5, -int(O.POT_FRUIT_JUICE)),
            (4, -int(O.POT_BOOZE)),
            (5, -int(O.POT_WATER)),
            (3, -int(O.ICE_BOX)),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        shknms=SHKFOODS,
    ),
    ShopType(
        name="jewelers",
        name2="ring shop",
        symb=ObjClass.RING,
        prob=3,
        shdist=D_SHOP,
        iprobs=(
            (85, int(ObjClass.RING)),
            (10, int(ObjClass.GEM)),
            (5, int(ObjClass.AMULET)),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        shknms=SHKRINGS,
    ),
    ShopType(
        name="quality apparel and accessories",
        name2="wand shop",
        symb=ObjClass.WAND,
        prob=3,
        shdist=D_SHOP,
        iprobs=(
            (90, int(ObjClass.WAND)),
            (5, -int(O.LEATHER_GLOVES)),
            (5, -int(O.ELVEN_CLOAK)),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        shknms=SHKWANDS,
    ),
    ShopType(
        name="hardware store",
        name2="tool shop",
        symb=ObjClass.TOOL,
        prob=3,
        shdist=D_SHOP,
        iprobs=((100, int(ObjClass.TOOL)),) + ((0, 0),) * 8,
        shknms=SHKTOOLS,
    ),
    ShopType(
        name="rare books",
        name2="bookstore",
        symb=ObjClass.SPBOOK,
        prob=3,
        shdist=D_SHOP,
        iprobs=((90, int(ObjClass.SPBOOK)), (10, int(ObjClass.SCROLL)))
        + ((0, 0),) * 7,
        shknms=SHKBOOKS,
    ),
    ShopType(
        name="health food store",
        name2="vegetarian food shop",
        symb=ObjClass.FOOD,
        prob=2,
        shdist=D_SHOP,
        iprobs=(
            (70, VEGETARIAN_CLASS),
            (20, -int(O.POT_FRUIT_JUICE)),
            (4, -int(O.POT_HEALING)),
            (3, -int(O.POT_FULL_HEALING)),
            (2, -int(O.SCR_FOOD_DETECTION)),
            (1, -int(O.LUMP_OF_ROYAL_JELLY)),
            (0, 0),
            (0, 0),
            (0, 0),
        ),
        shknms=SHKHEALTHFOODS,
    ),
    # Shops below this point are "unique": probability 0 by design,
    # created only via the special-level loader (C's comment).
    ShopType(
        name="lighting store",
        name2="lighting shop",
        symb=ObjClass.TOOL,
        prob=0,
        shdist=D_SHOP,
        iprobs=(
            (30, -int(O.WAX_CANDLE)),
            (44, -int(O.TALLOW_CANDLE)),
            (5, -int(O.BRASS_LANTERN)),
            (9, -int(O.OIL_LAMP)),
            (3, -int(O.MAGIC_LAMP)),
            (5, -int(O.POT_OIL)),
            (2, -int(O.WAN_LIGHT)),
            (1, -int(O.SCR_LIGHT)),
            (1, -int(O.SPE_LIGHT)),
        ),
        shknms=SHKLIGHT,
    ),
)

# C: shknam.c -- the sentinel row's prob is 0 and its name NULL; the
# Python list needs neither, so the row count is the shop-type count.
NUM_SHOPTYPES = len(SHOPTYPES)

# The number of rows *before* the unique shops: C counts them the same
# way in shkname()'s hallucination branch (`for (num = 0; ...; num++) if
# (shtypes[num].prob == 0) break;`).  This NetHack has one (the
# lighting store).
UNIQUE_SHOP_START = next(i for i, t in enumerate(SHOPTYPES) if t.prob == 0)

# The shop index of the health-food store (C: FODDERSHOP - SHOPBASE --
# the row whose iprobs names the VEGETARIAN_CLASS pseudo-class).
FODDER_SHOP = 10  # SHOPTYPES[FODDER_SHOP].name2 == "vegetarian food shop"

__all__ = [
    "D_SCATTER",
    "D_SHOP",
    "D_TEMPLE",
    "FODDER_SHOP",
    "NUM_SHOPTYPES",
    "SHKARMORS",
    "SHKBOOKS",
    "SHKFOODS",
    "SHKGENERAL",
    "SHKHEALTHFOODS",
    "SHKLIQUORS",
    "SHKLIGHT",
    "SHKRINGS",
    "SHKTOOLS",
    "SHKWANDS",
    "SHKWEAPONS",
    "SHOPTYPES",
    "ShopType",
    "UNIQUE_SHOP_START",
    "VEGETARIAN_CLASS",
]
