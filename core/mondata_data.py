"""The PM_ anchor table of core.mondata (extracted for readability).

This module holds the table of PM_ identifiers that used to live in
mondata.py, kept verbatim: one constant per monster type the
name-specific predicates in core.mondata refer to.  Each is resolved
from PM_NAMES (core.monst) at import time so a renumbering would
break loudly.  core.mondata imports them back from here; import
core.mondata, the public API, don't import this module directly.
"""
from __future__ import annotations

from .monst import PM_NAMES


def _pm(name: str) -> int:
    return PM_NAMES.index(name)


# ------------------------------------------------------------
# PM_ anchors referenced by name-specific predicates in core.mondata.
# Resolved from PM_NAMES at import time so a renumbering would break
# loudly.
# ------------------------------------------------------------

PM_AIR_ELEMENTAL = _pm("air elemental")
PM_BABY_GOLD_DRAGON = _pm("baby gold dragon")
PM_BABY_LONG_WORM = _pm("baby long worm")
PM_BABY_PURPLE_WORM = _pm("baby purple worm")
PM_BLACK_LIGHT = _pm("black light")
PM_BLACK_PUDDING = _pm("black pudding")
PM_BLACK_UNICORN = _pm("black unicorn")
PM_CHICKATRICE = _pm("chickatrice")
PM_CYCLOPS = _pm("Cyclops")
PM_DEATH = _pm("Death")
PM_DWARF = _pm("dwarf")
PM_ELF = _pm("elf")
PM_FAMINE = _pm("Famine")
PM_PESTILENCE = _pm("Pestilence")
PM_FIRE_ELEMENTAL = _pm("fire elemental")
PM_FIRE_VORTEX = _pm("fire vortex")
PM_FLAMING_SPHERE = _pm("flaming sphere")
PM_FLOATING_EYE = _pm("floating eye")
PM_GOLD_DRAGON = _pm("gold dragon")
PM_GOLD_GOLEM = _pm("gold golem")
PM_HORNED_DEVIL = _pm("horned devil")
PM_HUMAN = _pm("human")
PM_KI_RIN = _pm("ki-rin")
PM_LEATHER_GOLEM = _pm("leather golem")
PM_LONG_WORM = _pm("long worm")
PM_MASTER_MIND_FLAYER = _pm("master mind flayer")
PM_MEDUSA = _pm("Medusa")
PM_MIND_FLAYER = _pm("mind flayer")
PM_MINOTAUR = _pm("minotaur")
PM_MANES = _pm("manes")
PM_BALROG = _pm("balrog")
PM_ASMODEUS = _pm("Asmodeus")
PM_GREMLIN = _pm("gremlin")
PM_HORSE = _pm("horse")
PM_WARHORSE = _pm("warhorse")
PM_PONY = _pm("pony")
PM_PIRANHA = _pm("piranha")
PM_PURPLE_WORM = _pm("purple worm")
PM_ROCK_MOLE = _pm("rock mole")
PM_WOODCHUCK = _pm("woodchuck")
PM_RAVEN = _pm("raven")
PM_SALAMANDER = _pm("salamander")
PM_SHADE = _pm("shade")
PM_SHOCKING_SPHERE = _pm("shocking sphere")
PM_STALKER = _pm("stalker")
PM_STRAW_GOLEM = _pm("straw golem")
PM_PAPER_GOLEM = _pm("paper golem")
PM_WOOD_GOLEM = _pm("wood golem")
PM_IRON_GOLEM = _pm("iron golem")
PM_FLESH_GOLEM = _pm("flesh golem")
PM_GHOUL = _pm("ghoul")
PM_SKELETON = _pm("skeleton")
PM_TENGU = _pm("tengu")
PM_VAMPIRE_BAT = _pm("vampire bat")
PM_WHITE_UNICORN = _pm("white unicorn")
PM_GRAY_UNICORN = _pm("gray unicorn")
PM_GIANT = _pm("giant")
PM_ORC = _pm("orc")
PM_ETTIN = _pm("ettin")
PM_GNOME = _pm("gnome")
PM_KOBOLD = _pm("kobold")
PM_KOBOLD_ZOMBIE = _pm("kobold zombie")
PM_KOBOLD_MUMMY = _pm("kobold mummy")
PM_DWARF_ZOMBIE = _pm("dwarf zombie")
PM_DWARF_MUMMY = _pm("dwarf mummy")
PM_GNOME_ZOMBIE = _pm("gnome zombie")
PM_GNOME_MUMMY = _pm("gnome mummy")
PM_ORC_ZOMBIE = _pm("orc zombie")
PM_ORC_MUMMY = _pm("orc mummy")
PM_ELF_ZOMBIE = _pm("elf zombie")
PM_ELF_MUMMY = _pm("elf mummy")
PM_HUMAN_ZOMBIE = _pm("human zombie")
PM_HUMAN_MUMMY = _pm("human mummy")
PM_ETTIN_ZOMBIE = _pm("ettin zombie")
PM_ETTIN_MUMMY = _pm("ettin mummy")
PM_GIANT_ZOMBIE = _pm("giant zombie")
PM_GIANT_MUMMY = _pm("giant mummy")
PM_WATCHMAN = _pm("watchman")
PM_WATCH_CAPTAIN = _pm("watch captain")
PM_ARCHEOLOGIST = _pm("archeologist")
PM_WIZARD = _pm("wizard")
PM_BAT = _pm("bat")
PM_GIANT_BAT = _pm("giant bat")
PM_VAMPIRE = _pm("vampire")
PM_VAMPIRE_LEADER = _pm("vampire leader")

# defined further down in core.mondata (used by touch_petrifies /
# flesh_petrifies)
PM_COCKATRICE = _pm("cockatrice")
