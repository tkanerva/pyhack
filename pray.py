"""
Simplified Python implementation of NetHack's pray.c logic.
Assumes other game dependencies are implemented as stubs.
"""

import random
import time
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Dict
from enum import Enum, auto


# ============================================================
# ENUMS AND CONSTANTS
# ============================================================

class Alignment(Enum):
    NONE = 0
    LAWFUL = 1
    NEUTRAL = 2
    CHAOTIC = 3


class TroubleType(Enum):
    NONE = 0
    STONED = 14
    SLIMED = 13
    STRANGLED = 12
    LAVA = 11
    SICK = 10
    STARVING = 9
    STINKING_CLOUD = 8
    HIT = 7
    LYCANTHROPE = 6
    COLLAPSING = 5
    STUCK_IN_WALL = 4
    CURSED_LEVITATION = 3
    UNUSABLE_HANDS = 2
    CURSED_BLINDFOLD = 1
    PUNISHED = -1
    FUMBLING = -2
    CURSED_ITEMS = -3
    SADDLE = -4
    BLIND = -5
    POISONED = -6
    WOUNDED_LEGS = -7
    HUNGRY = -8
    STUNNED = -9
    CONFUSED = -10
    HALLUCINATION = -11


class PrayerResult(Enum):
    SUCCESS = 3
    DIFFERENT_ALTAR = 2
    TOO_SOON = 0
    TOO_NAUGHTY = 1
    UNDEAD_PRAYING = -1
    MOLCH_PRAYER = -2


class Race(Enum):
    HUMAN = "human"
    DEMON = "demon"
    UNDEAD = "undead"
    VAMPIRE = "vampire"
    UNICORN = "unicorn"
    WRAITH = "wraith"
    ZOMBIE = "zombie"
    GHOST = "ghost"
    MUMMY = "mummy"
    LICH = "lich"


class Role(Enum):
    PRIEST = "priest"
    KNIGHT = "knight"
    WIZARD = "wizard"
    MONK = "monk"
    HUMAN = "human"


# ============================================================
# STUB IMPLEMENTATIONS
# ============================================================

class StubGameEngine:
    """Stub for NetHack's game engine - other dependencies assumed implemented."""
    
    def __init__(self):
        self.moves = 0
        self.inhell = False
        self.random_seed = None
        
    def rnd(self, max_val: int) -> int:
        """Random number from 1 to max_val (inclusive)."""
        return random.randint(1, max_val)
    
    def rn1(self, base: int, offset: int = 1) -> int:
        """Random number between (1+offset) and (base+offset)."""
        return random.randint(1, base) + offset - 1
    
    def rnz(self, value: int) -> int:
        """Random number between 1 and value (inclusive)."""
        return self.rnd(value)
    
    def rn2(self, value: int) -> int:
        """Random number between 0 and value-1."""
        return random.randint(0, value - 1)
    
    def rnl(self, value: int) -> int:
        """Random number from 0 to value."""
        return random.randint(0, value)
    
    def min(self, a: int, b: int) -> int:
        return min(a, b)
    
    def max(self, a: int, b: int) -> int:
        return max(a, b)
    
    def xlev_to_rank(self, level: int) -> int:
        """Map level 1..30 to rank 0..8."""
        if level <= 5:
            return 0 if level <= 3 else 1
        elif level <= 13:
            return 2 if level <= 9 else 3
        elif level <= 21:
            return 4 if level <= 17 else 5
        elif level <= 29:
            return 6 if level <= 25 else 7
        else:
            return 8


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class PlayerState:
    """Simplified player state representing u struct from pray.c."""
    
    # Alignment
    align_type: Alignment = Alignment.NONE
    align_record: int = 0  # Piety level
    ublesscnt: int = 0  # Prayer cooldown
    ublessed: int = 0  # Blessed count
    ugangr: int = 0  # Anger with god
    
    # Hit points
    uhp: int = 100
    uhpmax: int = 100
    mh: int = 100  # Monster HP (if polymorphed)
    mhmax: int = 100
    ulevel: int = 1
    ulevelmax: int = 1
    
    # Status effects
    stoned: bool = False
    slimed: bool = False
    strangled: bool = False
    sick: bool = False
    blinded: bool = False
    deaf: bool = False
    stunned: bool = False
    confused: bool = False
    hallucination: bool = False
    lycanthrope: bool = False
    
    # Hunger/energy
    hunger_state: int = 0  # 0=satiated, 1=notHungry, 2=Hungry, 3=weak/WEAK, etc.
    
    # Conditions
    punished: bool = False
    trapped: bool = False
    trap_type: Optional[str] = None  # "lava", "buried_ball"
    in_wall: bool = False
    cursed_levitation: bool = False
    unusable_hands: bool = False
    cursed_blindfold: bool = False
    
    # Physical stats
    base_attrs: Dict[str, int] = field(default_factory=lambda: {
        'STR': 10, 'INT': 10, 'WIS': 10, 'DEX': 10, 'CON': 10, 'CHA': 10
    })
    max_attrs: Dict[str, int] = field(default_factory=lambda: {
        'STR': 18, 'INT': 18, 'WIS': 18, 'DEX': 18, 'CON': 18, 'CHA': 18
    })
    
    # Inventory
    inventory: List['Item'] = field(default_factory=list)
    wielded_weapon: Optional['Item'] = None
    armor: Dict[str, Optional['Item']] = field(default_factory=lambda: {
        'helmet': None, 'cloak': None, 'suit': None, 'gloves': None,
        'boots': None, 'shield': None, 'amulet': None,
        'left_ring': None, 'right_ring': None, 'blindfold': None
    })
    steed: Optional['Mount'] = None
    
    # Intrinsic powers
    passes_walls: bool = False
    reflecting: bool = False
    shock_resistance: bool = False
    disint_resistance: bool = False
    antimagic: bool = False
    telepat: bool = False
    fast: bool = False
    stealth: bool = False
    protection: bool = False
    see_invisible: bool = False
    fire_resistance: bool = False
    cold_resistance: bool = False
    sleep_resistance: bool = False
    poison_resistance: bool = False
    
    # Flags
    upolyd: bool = False  # Is polymorphed
    unchanging: bool = False
    flying: bool = False
    levitation: bool = False
    invisible: bool = False
    
    # Events
    uevent_hand_elbereth: int = 0  # 0=none, 1=Lawful, 2=Neutral, 3=Chaotic
    uevent_heard_tune: int = 0
    uevent_opened_dbridge: bool = False
    uevent_gehennom_entered: bool = False
    
    # Luck
    luck: int = 0
    ugifts: int = 0  # Number of divine gifts
    
    # Race and role
    race: Race = Race.HUMAN
    role: Role = Role.HUMAN
    gender_male: bool = True
    
    # Location
    x: int = 0
    y: int = 0
    
    # Prayer tracking
    praying: bool = False
    invulnerable: bool = False
    
    # Swallowing (eaten by monster)
    swallowed_by: Optional[str] = None


@dataclass
class Item:
    """Simplified item representation."""
    name: str
    otype: int
    oclass: int
    cursed: bool = False
    blessed: bool = False
    known: bool = False
    quantity: int = 1
    
    # Specific types
    is_weapon: bool = False
    is_armor: bool = False
    is_ring: bool = False
    is_amulet: bool = False
    is_potion: bool = False
    is_scroll: bool = False
    is_book: bool = False
    is_food: bool = False
    is_corpse: bool = False
    is_boulder: bool = False
    is_loadstone: bool = False
    is_gold: bool = False
    
    # Artifact
    is_artifact: bool = False
    artifact_name: Optional[str] = None


@dataclass
class Mount:
    """Player's steed."""
    name: str
    saddled: bool = False
    cursed_saddle: bool = False


@dataclass
class Monster:
    """Simplified monster."""
    name: str
    race: str  # Monster type code
    peaceful: bool = True
    is_undead: bool = False
    is_demon: bool = False
    is_vampshifter: bool = False
    is_tame: bool = False
    is_minion: bool = False
    hit_points: int = 0
    max_hit_points: int = 0


@dataclass
class AltarInfo:
    """Information about an altar."""
    alignment: Alignment
    is_high_altar: bool = False
    is_shrine: bool = False


# ============================================================
# PRAY ENGINE
# ============================================================

class PrayEngine:
    """
    Main prayer engine implementing pray.c logic.
    Assumes stub implementations for external dependencies.
    """
    
    def __init__(self, game: StubGameEngine):
        self.game = game
        self.player = PlayerState()
        self.altar_info: Optional[AltarInfo] = None
        self.p_type: int = 0  # Prayer type/result
        self.p_alignment: Alignment = Alignment.NONE
        self.p_trouble: int = 0
        
        # Trouble constants
        self.TROUBLE_STONED = 14
        self.TROUBLE_SLIMED = 13
        self.TROUBLE_STRANGLED = 12
        self.TROUBLE_LAVA = 11
        self.TROUBLE_SICK = 10
        self.TROUBLE_STARVING = 9
        self.TROUBLE_REGION = 8
        self.TROUBLE_HIT = 7
        self.TROUBLE_LYCANTHROPE = 6
        self.TROUBLE_COLLAPSING = 5
        self.TROUBLE_STUCK_IN_WALL = 4
        self.TROUBLE_CURSED_LEVITATION = 3
        self.TROUBLE_UNUSEABLE_HANDS = 2
        self.TROUBLE_CURSED_BLINDFOLD = 1
        self.TROUBLE_POISONED = 15
        self.TROUBLE_HUNGRY = 16
        self.TROUBLE_PUNISHED = 17
        self.TROUBLE_FUMBLING = 18
        self.TROUBLE_CURSED_ITEMS = 19
                
        # Alignment constants
        self.PIOUS = 20
        self.DEVOUT = 14
        self.FERVENT = 9
        self.STRIDENT = 4
    
    def on_altar(self) -> bool:
        """Check if player is on an altar."""
        return self.altar_info is not None
    
    def on_shrine(self) -> bool:
        """Check if player is on a shrine."""
        return self.altar_info and self.altar_info.is_shrine
    
    def get_altar_alignment(self) -> Alignment:
        """Get alignment of current altar."""
        return self.altar_info.alignment if self.altar_info else Alignment.NONE
    
    def critically_low_hp(self, only_if_injured: bool = False) -> bool:
        """Check if hit points are critically low."""
        curhp = self.player.mh if self.player.upolyd else self.player.uhp
        maxhp = self.player.mhmax if self.player.upolyd else self.player.uhpmax
        
        if only_if_injured and not (curhp < maxhp):
            return False
        
        hplim = 15 * self.player.ulevel
        if maxhp > hplim:
            maxhp = hplim
        
        divisor = self.game.xlev_to_rank(self.player.ulevel)
        if divisor <= 1:
            divisor = 5
        elif divisor <= 3:
            divisor = 6
        elif divisor <= 5:
            divisor = 7
        elif divisor <= 7:
            divisor = 8
        else:
            divisor = 9
        
        return curhp <= 5 or (curhp * divisor <= maxhp)
    
    def stuck_in_wall(self) -> bool:
        """Check if surrounded by impassable rock."""
        if self.player.passes_walls:
            return False
        # Stub: assume not stuck for simplicity
        return False
    
    def nohands(self, monster_data: str) -> bool:
        """Check if monster form has no hands."""
        # Stub
        return False
    
    def freehand(self) -> bool:
        """Check if player has free hands."""
        # Stub
        return not self.player.unusable_hands
    
    def isnum(self, value: int) -> bool:
        """Check if value is lycanthrope number."""
        # Stub
        return False
    
    def near_capacity(self) -> int:
        """Get encumbrance level."""
        # Stub
        return 0
    
    def region_danger(self) -> bool:
        """Check if in dangerous region (stinking cloud)."""
        # Stub
        return False
    
    def in_trouble(self) -> int:
        """
        Return trouble level: 0 if fine, positive for major trouble,
        negative for minor annoyances.
        """
        # Major troubles (checked first)
        if self.player.stoned:
            return self.TROUBLE_STONED
        if self.player.slimed:
            return self.TROUBLE_SLIMED
        if self.player.strangled:
            return self.TROUBLE_STRANGLED
        if self.player.trapped and self.player.trap_type == 'lava':
            return self.TROUBLE_LAVA
        if self.player.sick:
            return self.TROUBLE_SICK
        if self.player.hunger_state >= 3:  # WEAK
            return self.TROUBLE_STARVING
        if self.region_danger():
            return self.TROUBLE_REGION
        if (not self.player.upolyd or self.player.unchanging) and \
           self.critically_low_hp(False):
            return self.TROUBLE_HIT
        if self.isnum(1):  # Lycanthrope
            return self.TROUBLE_LYCANTHROPE
        if self.near_capacity() >= 3 and \
           (self.player.max_attrs['STR'] - self.player.base_attrs['STR']) > 3:
            return self.TROUBLE_COLLAPSING
        if self.stuck_in_wall():
            return self.TROUBLE_STUCK_IN_WALL
        if self.player.cursed_levitation:
            return self.TROUBLE_CURSED_LEVITATION
        if self.player.unusable_hands:
            return self.TROUBLE_UNUSEABLE_HANDS
        if self.player.blindfolded and self.player.armor['blindfold'] and \
           self.player.armor['blindfold'].cursed:
            return self.TROUBLE_CURSED_BLINDFOLD
        
        # Minor troubles
        if self.player.punished or (self.player.trapped and 
                                     self.player.trap_type == 'buried_ball'):
            return self.TROUBLE_PUNISHED
        if self.player.armor['gloves'] and self.player.armor['gloves'].cursed:
            return self.TROUBLE_FUMBLING
        
        # Check for cursed items
        if self.worst_cursed_item():
            return self.TROUBLE_CURSED_ITEMS
        
        if self.player.steed and self.player.steed.cursed_saddle:
            return self.TROUBLE_SADDLE
        
        if self.player.blinded_timeout > 1:
            return self.TROUBLE_BLIND
        
        # Check for stat debuffs
        for stat in ['STR', 'INT', 'WIS', 'DEX', 'CON', 'CHA']:
            if self.player.base_attrs[stat] < self.player.max_attrs[stat]:
                return self.TROUBLE_POISONED
        
        if self.player.wounded_legs and not self.player.steed:
            return self.TROUBLE_WOUNDED_LEGS
        
        if self.player.hunger_state >= 2:  # HUNGRY
            return self.TROUBLE_HUNGRY
        
        if self.player.stunned:
            return self.TROUBLE_STUNNED
        
        if self.player.confused:
            return self.TROUBLE_CONFUSED
        
        if self.player.hallucination:
            return self.TROUBLE_HALLUCINATION
        
        return 0
    
    def worst_cursed_item(self) -> Optional[Item]:
        """Find the worst cursed item."""
        # Check for loadstone if heavily encumbered
        if self.near_capacity() >= 2:
            for item in self.player.inventory:
                if item.cursed and item.is_loadstone:
                    return item
        
        # Weapon priority
        if self.player.wielded_weapon and self.player.wielded_weapon.cursed:
            return self.player.wielded_weapon
        
        # Gloves for rings
        if self.player.armor['gloves'] and self.player.armor['gloves'].cursed:
            return self.player.armor['gloves']
        
        # Shield
        if self.player.armor['shield'] and self.player.armor['shield'].cursed:
            return self.player.armor['shield']
        
        # Cloak
        if self.player.armor['cloak'] and self.player.armor['cloak'].cursed:
            return self.player.armor['cloak']
        
        # Suit
        if self.player.armor['suit'] and self.player.armor['suit'].cursed:
            return self.player.armor['suit']
        
        # Helmet (not opposite alignment)
        if self.player.armor['helmet'] and \
           self.player.armor['helmet'].cursed and \
           self.player.armor['helmet'].name != "Helmet of Opposite Alignment":
            return self.player.armor['helmet']
        
        # Boots
        if self.player.armor['boots'] and self.player.armor['boots'].cursed:
            return self.player.armor['boots']
        
        # Shirt
        if self.player.armor['suit'] and self.player.armor['suit'].cursed:
            return self.player.armor['suit']
        
        # Amulet
        if self.player.armor['amulet'] and self.player.armor['amulet'].cursed:
            return self.player.armor['amulet']
        
        # Rings
        if self.player.armor['left_ring'] and \
           self.player.armor['left_ring'].cursed:
            return self.player.armor['left_ring']
        if self.player.armor['right_ring'] and \
           self.player.armor['right_ring'].cursed:
            return self.player.armor['right_ring']
        
        # Blindfold
        if self.player.armor['blindfold'] and \
           self.player.armor['blindfold'].cursed:
            return self.player.armor['blindfold']
        
        return None
    
    def fix_curse_trouble(self, item: Optional[Item], what: Optional[str] = None):
        """Fix a cursed item issue."""
        if not item:
            return
        
        # Uncurse the item
        item.cursed = False
        item.blessed = True
        
        print(f"{'The ' if what else 'Your'}{item.name} softly glows!")
        
        # Handle specific cases
        if item.name == "Gloves of Fumbling":
            print("Your gloves are no longer slippery.")
        if item.name == "Blindfold":
            print("Your vision clears.")
    
    def fix_worst_trouble(self, trouble: int):
        """Fix a specific trouble type."""
        if trouble == self.TROUBLE_STONED:
            self.player.stoned = False
            print("You feel more limber.")
        
        elif trouble == self.TROUBLE_SLIMED:
            self.player.slimed = False
            print("The slime disappears.")
        
        elif trouble == self.TROUBLE_STRANGLED:
            if self.player.armor['amulet'] and \
               self.player.armor['amulet'].name == "Amulet of Strangulation":
                print("Your amulet vanishes!")
                self.player.armor['amulet'] = None
            print("You can breathe again.")
            self.player.strangled = False
        
        elif trouble == self.TROUBLE_LAVA:
            print("You are teleported to safety!")
            self.player.trapped = False
            self.player.trap_type = None
        
        elif trouble in (self.TROUBLE_STARVING, self.TROUBLE_HUNGRY):
            print("Your stomach feels content.")
            self.player.hunger_state = 0  # Satiated
        
        elif trouble == self.TROUBLE_SICK:
            print("You feel better.")
            self.player.sick = False
        
        elif trouble == self.TROUBLE_REGION:
            print("The stinking cloud dissipates.")
        
        elif trouble == self.TROUBLE_HIT:
            print("You feel much better.")
            maxhp = self.player.uhpmax
            if self.player.ulevel * 5 + 11 < maxhp:
                maxhp = self.player.ulevel * 5 + 11 + self.game.rnd(5)
            self.player.uhpmax = max(maxhp, 6)
            self.player.uhp = self.player.uhpmax
            if self.player.upolyd:
                self.player.mhmax = self.player.uhpmax
                self.player.mh = self.player.mhmax
        
        elif trouble == self.TROUBLE_COLLAPSING:
            print("You feel stronger.")
            self.player.base_attrs['STR'] = self.player.max_attrs['STR']
        
        elif trouble == self.TROUBLE_STUCK_IN_WALL:
            if random.random() > 0.5:
                print("Your surroundings change.")
            else:
                print("You feel much slimmer.")
                self.player.passes_walls = True
                # Stub: would set timeout
        
        elif trouble == self.TROUBLE_CURSED_LEVITATION:
            cursed_item = None
            if self.player.armor['boots'] and \
               self.player.armor['boots'].name == "Levitation Boots":
                cursed_item = self.player.armor['boots']
            elif self.player.armor['left_ring'] and \
                 self.player.armor['left_ring'].name == "Ring of Levitation":
                cursed_item = self.player.armor['left_ring']
            elif self.player.armor['right_ring'] and \
                 self.player.armor['right_ring'].name == "Ring of Levitation":
                cursed_item = self.player.armor['right_ring']
            
            if cursed_item:
                self.fix_curse_trouble(cursed_item)
                self.player.cursed_levitation = False
        
        elif trouble == self.TROUBLE_UNUSEABLE_HANDS:
            if self.player.wielded_weapon and self.player.wielded_weapon.cursed:
                self.fix_curse_trouble(self.player.wielded_weapon)
            elif self.player.upolyd and self.nohands("some_form"):
                if not self.player.unchanging:
                    print("Your shape becomes uncertain.")
                    self.player.upolyd = False
                else:
                    # Stub: unchanger logic
                    pass
        
        elif trouble == self.TROUBLE_CURSED_BLINDFOLD:
            self.fix_curse_trouble(self.player.armor['blindfold'])
        
        elif trouble == self.TROUBLE_LYCANTHROPE:
            print("You return to normal form.")
            self.player.lycanthrope = False
            self.player.upolyd = False
        
        elif trouble == self.TROUBLE_PUNISHED:
            print("Your chain disappears.")
            self.player.punished = False
            self.player.trapped = False
        
        elif trouble == self.TROUBLE_FUMBLING:
            if self.player.armor['gloves'] and \
               self.player.armor['gloves'].name == "Gloves of Fumbling":
                self.fix_curse_trouble(self.player.armor['gloves'])
            elif self.player.armor['boots'] and \
                 self.player.armor['boots'].name == "Fumble Boots":
                self.fix_curse_trouble(self.player.armor['boots'])
        
        elif trouble == self.TROUBLE_CURSED_ITEMS:
            cursed = self.worst_cursed_item()
            if cursed:
                self.fix_curse_trouble(cursed)
        
        elif trouble == self.TROUBLE_POISONED:
            print("You feel in good health again.")
            for stat in ['STR', 'INT', 'WIS', 'DEX', 'CON', 'CHA']:
                self.player.base_attrs[stat] = self.player.max_attrs[stat]
        
        elif trouble == self.TROUBLE_BLIND:
            if self.player.blinded:
                print("Your eyes feel better.")
                self.player.blinded = False
            if self.player.deaf:
                print("You can hear again.")
                self.player.deaf = False
        
        elif trouble == self.TROUBLE_WOUNDED_LEGS:
            print("Your legs heal.")
        
        elif trouble == self.TROUBLE_STUNNED:
            print("You clear your head.")
            self.player.stunned = False
        
        elif trouble == self.TROUBLE_CONFUSED:
            print("You focus your mind.")
            self.player.confused = False
        
        elif trouble == self.TROUBLE_HALLUCINATION:
            print("Looks like you are back in Kansas.")
            self.player.hallucination = False
    
    def god_zaps_you(self, resp_god: Alignment):
        """God zaps you with lightning/disintegration."""
        if self.player.swallowed_by:
            print("A bolt of lightning strikes the monster that ate you!")
            # Stub: monster dies
        else:
            print("A bolt of lightning strikes you!")
            if self.player.reflecting:
                print("It reflects from your shield!")
            elif self.player.shock_resistance:
                print("It seems not to affect you.")
            else:
                self._die_to_god(resp_god)
        
        print(f"{self._align_gname(resp_god)} is not deterred...")
        
        # Second attack: disintegration
        if not self.player.swallowed_by:
            print("A disintegration beam hits you!")
            if self.player.disint_resistance:
                print("You bask in its black glow for a minute...")
                print(f"{self._align_gname(resp_god)} says: 'I believe it not!'")
            else:
                self._die_to_god(resp_god)
    
    def _die_to_god(self, god: Alignment):
        """Player dies to god's wrath."""
        print(f"You fry to a crisp! The wrath of {self._align_gname(god)} has claimed you.")
        # Stub: game over
    
    def angry_gods(self, resp_god: Alignment):
        """Gods get angry at player."""
        self.player.ublessed = 0
        
        # Calculate max anger
        if resp_god != self.player.align_type:
            maxanger = self.player.align_record // 2 + (
                -self.player.luck // 3 if self.player.luck > 0 else -self.player.luck
            )
        else:
            maxanger = 3 * self.player.ugangr + (
                -self.player.luck // 3 if self.player.luck > 0 or 
                self.player.align_record >= self.STRIDENT 
                else -self.player.luck
            )
        
        maxanger = max(1, min(15, maxanger))
        
        action = self.game.rn2(maxanger)
        
        if action in (0, 1):
            print(f"You feel that {self._align_gname(resp_god)} is displeased.")
        
        elif action in (2, 3):
            self._god_voice(resp_god, None)
            print(f"\"Thou hast strayed from the path.\"")
            self._adjust_attr('WIS', -1)
            print("You lose experience.")
        
        elif action == 6:
            if not self.player.punished:
                self._angry_gods_internal(resp_god)
                print("You are punished!")
            else:
                self._angry_gods_internal(resp_god)
        
        elif action in (4, 5):
            self._angry_gods_internal(resp_god)
            print("Black glow surrounds you.")
            self._random_curse()
        
        elif action in (7, 8):
            self._god_voice(resp_god, None)
            print(f"\"Thou durst call upon me?\"")
            print(f"\"Then die, mortal!\"")
            # Stub: summon minion
            self._summon_minion(resp_god)
        
        else:
            self._angry_gods_internal(resp_god)
            self.god_zaps_you(resp_god)
        
        # Set prayer cooldown
        new_cooldown = self.game.rnz(300)
        self.player.ublesscnt = max(self.player.ublesscnt, new_cooldown)
    
    def _angry_gods_internal(self, god: Alignment):
        """Internal helper for angry gods."""
        self._god_voice(god, "Thou hast angered me.")
    
    def _random_curse(self):
        """Apply random curse."""
        # Stub: would find a random item and curse it
        print("A random item becomes cursed!")
    
    def _summon_minion(self, god: Alignment):
        """Summon a minion of the god."""
        # Stub
        print("A minion of the gods appears!")
    
    def _adjust_attr(self, attr: str, delta: int):
        """Adjust a stat attribute."""
        self.player.base_attrs[attr] = max(3, min(25, 
            self.player.base_attrs[attr] + delta))
    
    def _god_voice(self, god: Alignment, words: Optional[str]):
        """Print god's voice."""
        verbs = ["booms out", "thunders", "rings out", "booms"]
        verb = random.choice(verbs)
        
        if words:
            print(f"The voice of {self._align_gname(god)} {verb}: \"{words}\"")
        else:
            print(f"The voice of {self._align_gname(god)} {verb}:")
    
    def _align_gname(self, alignment: Alignment) -> str:
        """Get god name for alignment."""
        names = {
            Alignment.NONE: "Moloch",
            Alignment.LAWFUL: "Your Lawful God",
            Alignment.NEUTRAL: "Your Neutral God",
            Alignment.CHAOTIC: "Your Chaotic God",
        }
        return names.get(alignment, "Unknown")
    
    def at_your_feet(self, item_str: str):
        """Print item appearing at feet."""
        if self.player.blinded:
            item_str = "Something"
        if self.player.levitation:
            print(f"{item_str} appears beneath you!")
        else:
            print(f"{item_str} appears at your feet!")
    
    def gcrownu(self):
        """Crown player as Hand of Elbereth."""
        # Grant resistances
        self.player.see_invisible = True
        self.player.fire_resistance = True
        self.player.cold_resistance = True
        self.player.shock_resistance = True
        self.player.sleep_resistance = True
        self.player.poison_resistance = True
        
        self._god_voice(self.player.align_type, None)
        
        class_gift = "Strange Object"
        
        # Give class-specific gift
        if self.player.role == Role.WIZARD:
            class_gift = "Spell of Finger of Death"
        elif self.player.role == Role.MONK:
            class_gift = "Spell of Restore Ability"
        
        if class_gift.startswith("Spell"):
            print(f"You receive {class_gift.lower()}!")
        
        # Alignment-specific gifts
        if self.player.align_type == Alignment.LAWFUL:
            self.player.uevent_hand_elbereth = 1
            self._god_voice(self.player.align_type, "I crown thee... The Hand of Elbereth!")
            # Stub: give Excalibur
        
        elif self.player.align_type == Alignment.NEUTRAL:
            self.player.uevent_hand_elbereth = 2
            self._god_voice(self.player.align_type, "Thou shalt be my Envoy of Balance!")
            # Stub: give Vorpal Blade
        
        elif self.player.align_type == Alignment.CHAOTIC:
            self.player.uevent_hand_elbereth = 3
            self._god_voice(self.player.align_type, "Thou art chosen to steal souls for My Glory!")
            # Stub: give Stormbringer
    
    def give_spell(self):
        """Grant a spell to player."""
        # Stub: would create a spellbook or grant knowledge
        print("Divine knowledge fills your mind!")
    
    def pleased(self, g_align: Alignment):
        """God is pleased with player."""
        trouble = self.in_trouble()
        
        print(f"You feel that {self._align_gname(g_align)} is well-pleased.")
        
        # Wrong altar check
        if self.on_altar() and self.get_altar_alignment() != self.player.align_type:
            self._adjust_alignment(-1)
            return
        elif self.player.align_record < 2 and trouble <= 0:
            self._adjust_alignment(1)

        pat_on_head = 0
        # Determine action based on luck and piety
        if not trouble and self.player.align_record >= self.DEVOUT:
            pat_on_head = 1 if self.p_trouble == 0 else 0
        else:
            prayer_luck = max(self.player.luck, -1)
            action = self.game.rn1(prayer_luck + (3 if self.on_altar() else 2) + 
                                   (1 if self.on_shrine() else 0), 1)
            if not self.on_altar():
                action = min(action, 3)
            if self.player.align_record < self.STRIDENT:
                action = 1 if self.player.align_record > 0 or self.game.rnl(2) == 0 else 0
            
            action = min(action, 5)
            
            if action == 5:
                pat_on_head = 1
                # Fix all troubles
                while self.in_trouble() != 0:
                    self.fix_worst_trouble(self.in_trouble())
            elif action == 4:
                while self.in_trouble() != 0:
                    self.fix_worst_trouble(self.in_trouble())
            elif action == 3:
                # Fix up to 10 troubles
                for _ in range(10):
                    t = self.in_trouble()
                    if t <= 0:
                        break
                    self.fix_worst_trouble(t)
            elif action == 2:
                # Fix up to 9 troubles
                for _ in range(9):
                    t = self.in_trouble()
                    if t <= 0:
                        break
                    self.fix_worst_trouble(t)
            elif action == 1:
                if trouble > 0:
                    self.fix_worst_trouble(trouble)
            # action == 0: god ignores prayer
        
        # Pat on head special effects
        if pat_on_head:
            luck_modifier = (self.player.luck + 6) >> 1
            case = self.game.rn2(luck_modifier) if luck_modifier > 0 else 0
            
            if case == 1:
                # Bless or repair weapon
                if self.player.wielded_weapon:
                    if self.player.wielded_weapon.cursed:
                        self.fix_curse_trouble(self.player.wielded_weapon)
                    elif not self.player.wielded_weapon.blessed:
                        self.player.wielded_weapon.blessed = True
                        print("Your weapon glows with a light blue aura!")
                    # Repair damage
                    self.player.wielded_weapon.oeroded = 0
                    self.player.wielded_weapon.oeroded2 = 0
                    print("Your weapon is as good as new!")
            
            elif case == 2:
                # Full healing and level restoration
                if not self.player.blinded:
                    print("You are surrounded by golden glow.")
                
                if self.player.ulevel < self.player.ulevelmax:
                    self.player.ulevelmax -= 1
                    # Stub: pluslvl
                    print("You regain a level!")
                else:
                    self.player.uhpmax += 5
                    self.player.uhp = self.player.uhpmax
                    if self.player.upolyd:
                        self.player.mhmax += 5
                        self.player.mh = self.player.mhmax
                
                if self.player.base_attrs['STR'] < self.player.max_attrs['STR']:
                    self.player.base_attrs['STR'] = self.player.max_attrs['STR']
                
                if self.player.hunger_state < 900:
                    self.player.hunger_state = 0  # Satiated
                
                if self.player.luck < 0:
                    self.player.luck = 0
                
                self.player.blinded = False
                self.player.blinded_timeout = 0
            
            elif case == 4:
                # Uncurse all inventory
                if self.player.blinded:
                    print("You feel the power of the gods.")
                else:
                    print("You are surrounded by a light blue aura.")
                
                uncursed_count = 0
                for item in self.player.inventory:
                    if item.cursed:
                        if self.player.armor['helmet'] and \
                           item.name == "Helmet of Opposite Alignment":
                            continue
                        item.cursed = False
                        item.blessed = True
                        if not self.player.blinded:
                            print(f"{item.name} softly glows!")
                        uncursed_count += 1
                
                if uncursed_count > 0:
                    print("Your cursed items are now blessed!")
            
            elif case == 5:
                # Grant intrinsic power
                self._god_voice(self.player.align_type, 
                               "Thou hast pleased me with thy progress!")
                
                if not self.player.telepat:
                    self.player.telepat = True
                    print("You are granted Telepathy!")
                elif not self.player.fast:
                    self.player.fast = True
                    print("You are granted Speed!")
                elif not self.player.stealth:
                    self.player.stealth = True
                    print("You are granted Stealth!")
                else:
                    if not self.player.protection:
                        self.player.protection = True
                        if not self.player.ublessed:
                            self.player.ublessed = self.game.rn1(3, 2)
                    else:
                        self.player.ublessed += 2
                    print("You are granted the protection of the gods!")
            
            elif case in (7, 8):
                if self.player.align_record >= self.PIOUS and \
                   not self.player.uevent_hand_elbereth:
                    self.gcrownu()
            
            elif case == 6:
                self.give_spell()
        
        # Set prayer cooldown
        self.player.ublesscnt = self.game.rnz(350)
        
        # Add bonus for Hand of Elbereth
        if self.player.uevent_hand_elbereth:
            self.player.ublesscnt += self.player.uevent_hand_elbereth * \
                self.game.rnz(1000)
    
    def _adjust_alignment(self, delta: int):
        """Adjust alignment piety."""
        self.player.align_record = max(-99, min(99, 
            self.player.align_record + delta))
    
    def water_prayer(self, bless: bool) -> bool:
        """Bless or curse water on altar."""
        # Stub: would find potions/water on altar
        print("Potions on the altar glow blue (blessed) or black (cursed)!")
        return True
    
    def gods_upset(self, g_align: Alignment):
        """God is upset with player."""
        if g_align == self.player.align_type:
            self.player.ugangr += 1
        elif self.player.ugangr > 0:
            self.player.ugangr -= 1
        
        self.angry_gods(g_align)
    
    def desecrate_altar(self, high_altar: bool, altar_align: Alignment):
        """Desecrate an altar."""
        if altar_align == self.player.align_type:
            self._adjust_alignment(-20)
            self.player.ugangr += 5
        
        print("You feel the air grow charged...")
        print(f"{self._align_gname(altar_align)} has noticed you!")
        print(f"So, mortal! You dare desecrate my {'High Temple' if high_altar else 'altar'}!")
        
        self.god_zaps_you(altar_align)
    
    def offer_corpse(self, corpse: Item, high_altar: bool, altar_align: Alignment):
        """Offer a corpse as sacrifice."""
        # Check conduct
        self.player.gnostic_conduct = True  # Stub
        
        # Check for same race sacrifice (strongly discouraged)
        if corpse.corpse_race == self.player.race:
            self.sacrifice_your_race(corpse, high_altar, altar_align)
            return
        
        # Check for pet sacrifice
        if corpse.is_tame:
            print("So this is how you repay loyalty?")
            self._adjust_alignment(-3)
            self.haggravate_monster = True  # Stub
            self.offer_negative_valued(high_altar, altar_align)
            return
        
        # Evaluate offering value
        value = self.eval_offering(corpse, altar_align)
        
        if value == 0:
            print("Nothing happens.")
            return
        elif value < 0:
            self.offer_negative_valued(high_altar, altar_align)
            return
        
        # Different altar alignment
        if altar_align != self.player.align_type:
            if high_altar:
                self.desecrate_altar(high_altar, altar_align)
            else:
                self.offer_different_alignment_altar(corpse, altar_align)
            return
        
        # Consume offering
        print(f"Your sacrifice is consumed in a flash of light!")
        
        if self.player.ugangr > 0:
            saved_anger = self.player.ugangr
            reduction = (value * (3 if self.player.align_type != Alignment.CHAOTIC else 2)) // 24
            self.player.ugangr = max(0, self.player.ugangr - reduction)
            
            if self.player.ugangr < saved_anger:
                if self.player.ugangr:
                    print("Your god seems slightly mollified.")
                    if self.player.luck < 0:
                        self.player.luck += 1
                else:
                    print("Your god seems mollified.")
                    if self.player.luck < 0:
                        self.player.luck = 0
        elif self.player.align_record < 0:  # Angry
            if value > 24:
                value = 24
            if value > -self.player.align_record:
                value = -self.player.align_record
            self._adjust_alignment(value)
            print("You feel partially absolved.")
        elif self.player.ublesscnt > 0:
            saved_cnt = self.player.ublesscnt
            reduction = (value * (500 if self.player.align_type == Alignment.CHAOTIC else 300)) // 24
            self.player.ublesscnt = max(0, self.player.ublesscnt - reduction)
            
            if self.player.ublesscnt < saved_cnt:
                if self.player.ublesscnt:
                    print("You have a hopeful feeling.")
                    if self.player.luck < 0:
                        self.player.luck += 1
                else:
                    print("You have a feeling of reconciliation.")
                    if self.player.luck < 0:
                        self.player.luck = 0
        else:
            # May bestow artifact
            if self.bestow_artifact(value):
                return
            
            orig_luck = self.player.luck
            luck_increase = (value * 20) // (24 * 2)  # LUCKMAX approx 20
            
            if orig_luck > value:
                luck_increase = 0
            elif orig_luck + luck_increase > value:
                luck_increase = value - orig_luck
            
            self.player.luck += luck_increase
            if self.player.luck < 0:
                self.player.luck = 0
            
            if self.player.luck != orig_luck:
                if self.player.blinded:
                    print("You think something brushed your foot.")
                else:
                    print("You glimpse a four-leaf clover at your feet!")
    
    def eval_offering(self, corpse: Item, altar_align: Alignment) -> int:
        """Evaluate value of a sacrifice."""
        if not corpse.corpse_name:
            return 0
        
        value = 10  # Stub: base value
        
        # Undead bonus
        if corpse.is_undead and self.player.align_type != Alignment.CHAOTIC:
            value += 1
        
        # Unicorn bonus/penalty
        if corpse.corpse_name == "unicorn":
            unicalign = 1 if corpse.alignment >= 0 else -1  # Stub
            if unicalign == altar_align.value:
                print("Such an action is an insult!")
                self._adjust_attr('WIS', -1)
                return -1
            elif self.player.align_type == altar_align:
                if self.player.align_record < 30:
                    print("You feel appropriately aligned.")
                else:
                    print("You are thoroughly on the right path.")
                self._adjust_alignment(5)
                value += 3
        
        return value
    
    def sacrifice_your_race(self, corpse: Item, high_altar: bool, 
                           altar_align: Alignment):
        """Sacrifice your own race (terrible idea)."""
        if self.player.race == Race.DEMON:
            print("You find the idea very satisfying.")
        else:
            print("You'll regret this infamous offense!")
        
        if high_altar and altar_align != Alignment.CHAOTIC:
            self.desecrate_altar(high_altar, altar_align)
        elif altar_align != Alignment.CHAOTIC and altar_align != Alignment.NONE:
            print("The altar is stained with your blood.")
            # Stub: change altar alignment
            self.angry_priest()  # Stub
        
        if self.player.align_type != Alignment.CHAOTIC:
            self._adjust_alignment(-5)
            self.player.ugangr += 3
            self._adjust_attr('WIS', -1)
            self.angry_gods(self.player.align_type)
            self.player.luck -= 5
        else:
            self._adjust_alignment(5)
    
    def bestow_artifact(self, max_value: int) -> bool:
        """Possibly bestow an artifact."""
        if self.player.ulevel > 2 and self.player.luck >= 0:
            # Chance decreases with more gifts and more artifacts
            if not random.random() < (1 / (6 + 2 * self.player.ugifts * 10)):
                return False
            
            print("You are bestowed with an artifact!")
            self.player.ugifts += 1
            self.player.ublesscnt = self.game.rnz(300 + 500)
            print("Use my gift wisely!")
            
            # Stub: grant artifact
            return True
        
        return False
    
    def offer_different_alignment_altar(self, item: Item, altar_align: Alignment):
        """Offer at altar of different alignment."""
        if self.player.align_record < 0 or \
           (altar_align == Alignment.NONE and self.game.inhell):
            # Conversion attempt
            if self.player.align_base_current == self.player.align_base_original:
                print("You have a strong feeling that your god is angry...")
                print(f"{self._align_gname(altar_align)} accepts your allegiance.")
                # Stub: convert alignment
                self.player.luck -= 3
                self.player.ublesscnt += 300
            else:
                self.player.ugangr += 3
                self._adjust_alignment(-5)
                print(f"{self._align_gname(altar_align)} rejects your sacrifice!")
                print("Suffer, infidel!")
                self.player.luck -= 5
                self._adjust_attr('WIS', -2)
                if not self.game.inhell:
                    self.angry_gods(self.player.align_type)
        else:
            # Conflict - altar may change alignment
            print(f"You sense a conflict between {self._align_gname(self.player.align_type)} and {self._align_gname(altar_align)}.")
            
            if self.game.rnl(8 + self.player.ulevel) > 5:
                print("You feel the power of your god increase.")
                self.player.luck += 1
                
                # Change altar alignment
                # Stub: change altar mask
                print("The altar glows!")
                
                if self.game.rnl(self.player.ulevel) > 6 and \
                   self.player.align_record > 0 and \
                   self.game.rnd(self.player.align_record) > 22:
                    self._summon_minion(altar_align)
            else:
                print("Unluckily, you feel the power of your god decrease.")
                self.player.luck -= 1
    
    def offer_negative_valued(self, high_altar: bool, altar_align: Alignment):
        """Handle negative value offering."""
        if altar_align != self.player.align_type and high_altar:
            self.desecrate_altar(high_altar, altar_align)
        else:
            self.gods_upset(altar_align)
    
    def can_pray(self, praying: bool = True) -> bool:
        """Check if player can pray."""
        # Set up prayer type and alignment
        self.p_alignment = self.get_altar_alignment() if self.on_altar() else self.player.align_type
        self.p_trouble = self.in_trouble()
        
        # Demon checking
        if self.player.race == Race.DEMON and \
           (self.p_alignment == Alignment.LAWFUL or 
            (self.p_alignment == Alignment.NEUTRAL and 
             self.p_alignment != Alignment.CHAOTIC)):
            if praying:
                print("The very idea of praying to a lawful/neutral god is repugnant to you.")
            return False
        
        if praying:
            print(f"You begin praying to {self._align_gname(self.p_alignment)}.")
        
        # Calculate alignment factor
        if self.player.align_type and self.player.align_type == -self.p_alignment.value:
            alignment = -self.player.align_record
        elif self.player.align_type != self.p_alignment:
            alignment = self.player.align_record // 2
        else:
            alignment = self.player.align_record
        
        # Determine prayer type
        if self.p_alignment == Alignment.NONE:  # Moloch
            self.p_type = -2
        elif (self.p_trouble > 0 and self.player.ublesscnt > 200) or \
             (self.p_trouble < 0 and self.player.ublesscnt > 100) or \
             (self.p_trouble == 0 and self.player.ublesscnt > 0):
            self.p_type = 0  # Too soon
        elif self.player.luck < 0 or self.player.ugangr or alignment < 0:
            self.p_type = 1  # Too naughty
        else:
            if self.on_altar() and self.player.align_type != self.p_alignment:
                self.p_type = 2  # Different altar
            else:
                self.p_type = 3  # Good to pray
        
        # Undead checking
        if self.player.race == Race.UNDEAD and not self.game.inhell and \
           (self.p_alignment == Alignment.LAWFUL or 
            (self.p_alignment == Alignment.NEUTRAL and self.game.rn2(10) == 0)):
            self.p_type = -1
        
        return self.p_type == 3 or not praying
    
    def pray_revive(self) -> bool:
        """Check if prayer revives a pet."""
        # Stub: check for pet corpse on altar
        return False
    
    def dopray(self) -> str:
        """Handle #pray command."""
        # Paranoid prayer check (stub)
        
        self.player.gnostic_conduct = True  # Stub
        
        if not self.can_pray(True):
            return "FAILED"
        
        # Wizard cheat (stub)
        
        # Begin praying animation
        self.player.praying = True
        self.player.invulnerable = True
        
        if self.p_type == 3 and not self.game.inhell:
            if not self.player.blinded:
                print("You are surrounded by a shimmering light.")
        
        return "TIME"
    
    def prayer_done(self):
        """Handle end of prayer."""
        self.player.praying = False
        self.player.invulnerable = False
        
        if self.p_type == -2:  # Moloch prayer outside Gehennom
            print("You hear diabolical laughter all around you...")
            self._adjust_alignment(-2)
            if not self.game.inhell:
                print("Nothing else happens.")
                return
        elif self.p_type == -1:  # Undead prayer
            if self.p_alignment == Alignment.LAWFUL:
                self._god_voice(self.p_alignment, 
                               "Vile creature, thou durst call upon me?")
            else:
                self._god_voice(self.p_alignment, 
                               "Walk no more, perversion of nature!")
            print("You feel like you are falling apart.")
            self.player.upolyd = False
            print("You lose some hit points.")
            return
        
        if self.game.inhell:
            print(f"Since you are in Gehennom, {self._align_gname(self.p_alignment)} "
                  f"can't help you.")
            if self.player.align_record <= 0 or self.game.rnl(self.player.align_record):
                self.angry_gods(self.player.align_type)
            return
        
        if self.p_type == 0:  # Too soon
            if self.on_altar() and self.player.align_type != self.p_alignment:
                self.water_prayer(False)
            self.player.ublesscnt += self.game.rnz(250)
            self.player.luck -= 3
            self.gods_upset(self.player.align_type)
        elif self.p_type == 1:  # Too naughty
            if self.on_altar() and self.player.align_type != self.p_alignment:
                self.water_prayer(False)
            self.angry_gods(self.player.align_type)
        elif self.p_type == 2:  # Different altar
            if self.water_prayer(False):
                self.player.ublesscnt += self.game.rnz(250)
                self.player.luck -= 3
                self.gods_upset(self.player.align_type)
            else:
                self.pleased(self.p_alignment)
        else:  # Good to pray (type 3)
            if self.on_altar():
                self.pray_revive()
                self.water_prayer(True)
            self.pleased(self.p_alignment)
    
    def doturn(self) -> str:
        """Handle #turn command (turn undead)."""
        if self.player.role not in (Role.PRIEST, Role.KNIGHT):
            if hasattr(self, 'known_spell') and self.known_spell("turn_undead"):
                return "SPELL"
            print("You don't know how to turn undead!")
            return "FAILED"
        
        self.player.gnostic_conduct = True  # Stub
        
        if not self.can_chant():
            print("You are incapable of calling upon the gods to turn aside evilness.")
            return "FAILED"
        
        if (self.player.align_type != Alignment.CHAOTIC and 
            (self.player.race == Race.DEMON or 
             self.player.race == Race.UNDEAD)):
            print("For some reason, the gods seem to ignore you.")
            self.aggravate()  # Stub
            return "TIME"
        
        if self.game.inhell:
            print("Since you are in Gehennom, the gods can't help you.")
            self.aggravate()  # Stub
            return "TIME"
        
        print(f"Calling upon {self._align_gname(self.player.align_type)}, "
              f"you chant an arcane formula.")
        
        # Turn undead logic
        range = 8 + self.player.ulevel // 5
        range *= range
        
        # Stub: iterate monsters and turn/flee/kill undead
        
        # Paralysis
        duration = -(5 - (self.player.ulevel - 1) // 6)
        print("You are momentarily paralyzed.")
        
        return "TIME"
    
    def can_chant(self) -> bool:
        """Check if player can chant."""
        # Stub
        return not self.player.strangled
    
    def aggravate(self):
        """Aggravate monsters."""
        # Stub
        pass
    
    def known_spell(self, spell: str) -> bool:
        """Check if player knows a spell."""
        # Stub
        return False


# ============================================================
# EXAMPLE USAGE
# ============================================================

def example_pray_session():
    """Demonstrate the prayer engine."""
    game = StubGameEngine()
    engine = PrayEngine(game)
    
    print("=" * 60)
    print("NetHack Prayer Engine - Python Implementation")
    print("=" * 60)
    
    # Setup player
    engine.player.align_type = Alignment.LAWFUL
    engine.player.align_record = 10  # Fervent
    engine.player.ulevel = 5
    engine.player.luck = 5
    engine.player.ublesscnt = 0
    engine.player.sick = False
    engine.player.stoned = False
    engine.player.angry_god = False
    engine.player.blindfolded = False
    engine.player.blinded_timeout = 0
    engine.player.wounded_legs = False
    
    # Scenario 1: Successful prayer
    print("\n--- Scenario 1: Successful Prayer ---")
    engine.player.uhp = 50
    engine.player.uhpmax = 100
    print(engine.player)
    result = engine.dopray()
    if result == "TIME":
        engine.prayer_done()
    
    # Scenario 2: Prayer when angry
    print("\n--- Scenario 2: Prayer When Angry ---")
    engine.player.ugangr = 5
    engine.player.luck = -2
    engine.dopray()
    
    # Scenario 3: Prayer on altar
    print("\n--- Scenario 3: Prayer on Aligned Altar ---")
    engine.altar_info = AltarInfo(Alignment.LAWFUL, is_shrine=False)
    engine.player.ublesscnt = 0
    engine.player.align_record = 15  # Devout
    engine.dopray()
    if engine.dopray() == "TIME":
        engine.prayer_done()
    
    # Scenario 4: Prayer on wrong altar
    print("\n--- Scenario 4: Prayer on Wrong Altar ---")
    engine.altar_info = AltarInfo(Alignment.CHAOTIC)
    engine.player.ublesscnt = 0
    engine.dopray()
    
    # Scenario 5: God pleases player
    print("\n--- Scenario 5: God Pleases Player (Major Help) ---")
    engine.altar_info = AltarInfo(Alignment.LAWFUL)
    engine.player.ublesscnt = 0
    engine.player.align_record = 25  # Pious
    engine.player.sick = True
    engine.player.hunger_state = 3  # Weak
    engine.dopray()
    if engine.dopray() == "TIME":
        engine.prayer_done()
    
    print("\n" + "=" * 60)
    print("Demo complete!")


if __name__ == "__main__":
    example_pray_session()

