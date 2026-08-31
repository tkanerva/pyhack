"""
NetHack priest.py - Object-oriented Python implementation of priest.c
Assumes dependencies are implemented as stubs
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Callable


# --- Alignment Constants ---
ALGN_LAWFUL = 1
ALGN_NEUTRAL = 0
ALGN_CHAOTIC = -1
ALGN_SINNED = -4  # worse than strayed
ALGN_DEVOUT = 14  # better than fervent

# --- Room/Level Stubs ---
class Level:
    def __init__(self, d_level: int = 0):
        self.d_level = d_level
    
    def __eq__(self, other):
        if not isinstance(other, Level):
            return False
        return self.d_level == other.d_level

class Coord:
    def __init__(self, x: int = 0, y: int = 0):
        self.x = x
        self.y = y

# --- Data Structures ---
@dataclass
class EpriData:
    """Priest-specific extra data"""
    parentmid: int = 0
    shroom: Optional[str] = None  # shrine room identifier
    shralign: int = 0  # shrine alignment
    shrpos: Coord = field(default_factory=Coord)
    shrlevel: Optional[Level] = None
    intone_time: int = 0
    enter_time: int = 0
    peaceful_time: int = 0
    hostile_time: int = 0
    cheapskate_count: int = 0


@dataclass
class EminData:
    """Minion-specific extra data"""
    min_align: int = 0
    renegade: bool = False


class Monster:
    """Base monster class with priest/minion support"""
    
    def __init__(self, name: str, align: int, x: int = 0, y: int = 0):
        self.name = name
        self.x = x
        self.y = y
        self.m_id: int = random.randint(1, 10000)
        self.mextra: Optional[object] = None  # epri or emin
        self.ispriest: bool = False
        self.isminion: bool = False
        self.mpeaceful: bool = True
        self.mconf: bool = False  # confused
        self.mcansee: bool = True
        self.mtame: bool = False
        self.mflee: bool = False
        self.minvis: bool = False
        self.msleeping: bool = False
        self.mfrozen: int = 0
        self.mcanmove: bool = True
        self.malign: int = align
        
        # For shopkeepers
        self.isshk: bool = False
        self.isminion: bool = False
    
    def set_priest_data(self):
        """Initialize priest extra data"""
        if not self.ispriest:
            self.mextra = EpriData(parentmid=self.m_id)
            self.ispriest = True
    
    def set_minion_data(self, align: int, renegade: bool = False):
        """Initialize minion extra data"""
        if not self.isminion:
            self.mextra = EminData(min_align=align, renegade=renegade)
            self.isminion = True
    
    def epri(self) -> Optional[EpriData]:
        """Get priest data"""
        if self.ispriest and isinstance(self.mextra, EpriData):
            return self.mextra
        return None
    
    def emin(self) -> Optional[EminData]:
        """Get minion data"""
        if self.isminion and isinstance(self.mextra, EminData):
            return self.mextra
        return None
    
    def free_epri(self):
        """Free priest data"""
        if self.ispriest and self.mextra:
            self.mextra = None
            self.ispriest = False
        self.mpeaceful = True  # Reset peaceful state
    
    def get_alignment(self) -> int:
        """Get monster's alignment type"""
        if self.ispriest:
            epri = self.epri()
            if epri:
                align = epri.shralign
                return ALGN_LAWFUL if align > 0 else (ALGN_CHAOTIC if align < 0 else ALGN_NEUTRAL)
        elif self.isminion:
            emin = self.emin()
            if emin:
                align = emin.min_align
                return ALGN_LAWFUL if align > 0 else (ALGN_CHAOTIC if align < 0 else ALGN_NEUTRAL)
        return self.malign


class PriestMonster(Monster):
    """Priest-specific monster with temple logic"""
    
    def __init__(self, name: str, align: int, x: int = 0, y: int = 0):
        super().__init__(name, align, x, y)
        self.set_priest_data()
    
    def can_move_special(self, target_x: int, target_y: int, avoid: bool = True) -> int:
        """
        Move for priests. Returns:
        1: moved, 0: didn't move, -1: let default move handle, -2: died
        """
        if self.x == target_x and self.y == target_y:
            return 0
        
        # If confused, don't avoid
        if self.mconf:
            avoid = False
        
        # Simple movement logic (simplified from C)
        if self._can_move_to(target_x, target_y, avoid):
            self.x = target_x
            self.y = target_y
            return 1
        
        return 0
    
    def _can_move_to(self, x: int, y: int, avoid: bool) -> bool:
        """Check if monster can move to position"""
        # Simplified - in real implementation would check walls, other monsters, etc.
        return True
    
    def pri_move(self) -> int:
        """
        Priest movement logic.
        Returns: 1: moved, 0: didn't, -1: default move, -2: died
        """
        epri = self.epri()
        if not epri or not epri.shrpos:
            return -1
        
        omx, omy = self.x, self.y
        avoid = True
        
        # Check if at temple
        if not self._histemple_at(omx, omy):
            return -1
        
        ggx = epri.shrpos.x + random.randint(-1, 1)
        ggy = epri.shrpos.y + random.randint(-1, 1)
        
        # Check if aggressive
        if not self.mpeaceful:
            # If player nearby, attack
            if self._is_near_player():
                self.mattack_player()
                return 0
            # Chase player in temple
            elif self._is_in_temple_room(epri.shroom):
                if self.mcansee and self._can_see_player():
                    ggx = player.x
                    ggy = player.y
                avoid = False
        
        return self.can_move_special(ggx, ggy, avoid)
    
    def _histemple_at(self, x: int, y: int) -> bool:
        """Check if at temple"""
        epri = self.epri()
        return (epri is not None and 
                epri.shroom is not None and
                epri.shrpos is not None and
                x == epri.shrpos.x and 
                y == epri.shrpos.y)
    
    def _is_near_player(self) -> bool:
        """Check if near player"""
        return abs(self.x - player.x) <= 1 and abs(self.y - player.y) <= 1
    
    def _is_in_temple_room(self, room_id: str) -> bool:
        """Check if in temple room"""
        return room_id in player.urooms
    
    def _can_see_player(self) -> bool:
        """Check if can see player"""
        # Simplified line-of-sight
        return True
    
    def mattack_player(self):
        """Attack the player"""
        print(f"{self._priestname(True)} attacks you!")
    
    def _priestname(self, reveal_high: bool = False) -> str:
        """Get priest's name with proper articles and modifiers"""
        # Simplified version of priestname()
        if self.minvis:
            return "an invisible " + self.name
        return f"the {self.name}"


class RoamerMonster(Monster):
    """Roaming minion (not tied to a specific shrine)"""
    
    def __init__(self, name: str, align: int, x: int = 0, y: int = 0, peaceful: bool = True):
        super().__init__(name, align, x, y)
        self.set_minion_data(align, renegade=(player.get_alignment() == align and not peaceful))
        self.mpeaceful = peaceful
    
    def reset_hostility(self):
        """Reset hostility based on alignment"""
        emin = self.emin()
        if not emin:
            return
        
        if emin.min_align != player.get_alignment():
            self.mpeaceful = False
            self.mtame = False


class Temple:
    """Temple/shrine management"""
    
    def __init__(self, room_id: str, x: int = 0, y: int = 0):
        self.room_id = room_id
        self.shrine_pos = Coord(x, y)
        self.level: Optional[Level] = None
        self.alignment: int = 0
        self.priest: Optional[PriestMonster] = None
        self.is_sanctum: bool = False
    
    def has_shrine(self) -> bool:
        """Check if shrine exists and is properly aligned"""
        if not self.priest:
            return False
        epri = self.priest.epri()
        if not epri:
            return False
        
        # Simplified shrine check
        return epri.shralign == self.alignment
    
    def is_holy_temple(self, priest: PriestMonster) -> bool:
        """Check if in holy temple"""
        if not priest.ispriest:
            return False
        if not self._histemple_at(priest, priest.x, priest.y):
            return False
        return self.has_shrine(priest)
    
    def _histemple_at(self, priest: PriestMonster, x: int, y: int) -> bool:
        """Check if priest is at temple"""
        epri = priest.epri()
        return (epri is not None and 
                epri.shroom == self.room_id and
                x == self.shrine_pos.x and 
                y == self.shrine_pos.y)


class Player:
    """Player character with alignment"""
    
    def __init__(self):
        self.x = 0
        self.y = 0
        self.ualign_type: int = ALGN_NEUTRAL
        self.ualign_record: int = 0
        self.urooms: List[str] = []
        self.invent_gold: int = 0
        self.ublessed: int = 0
        self.HClairvoyant: int = 0
        self.HProtection: int = 0
        self.ucleansed: int = 0
        self.ulevelpeak: int = 1
    
    def get_alignment(self) -> int:
        return self.ualign_type
    
    def is_coaligned(self, priest: PriestMonster) -> bool:
        """Check if player is coaligned with priest"""
        return self.ualign_type == priest.get_alignment()
    
    def can_donate(self, amount: int) -> bool:
        """Check if player can donate gold"""
        return self.invent_gold >= amount
    
    def donate_gold(self, amount: int):
        """Donate gold to temple"""
        self.invent_gold -= amount


# --- Global Player Instance ---
player = Player()


# --- Temple Functions ---

def temple_occupied(rooms: List[str]) -> Optional[str]:
    """Check if any temple room is occupied"""
    for room in rooms:
        if "temple" in room.lower():
            return room
    return None


def find_priest(room_id: str, temples: Dict[str, Temple]) -> Optional[PriestMonster]:
    """Find priest in a specific temple room"""
    temple = temples.get(room_id)
    if temple and temple.priest:
        return temple.priest
    return None


def priest_talk(priest: PriestMonster):
    """Handle conversation with priest"""
    coaligned = player.is_coaligned(priest)
    strayed = player.ualign_record < ALGN_SINNED
    
    # Check if priest wants to talk
    if priest.mflee or (not priest.ispriest and coaligned and strayed):
        print(f"{priest.name} doesn't want anything to do with you!")
        priest.mpeaceful = False
        return
    
    # Priest only chats if peaceful and in their temple
    temple = None  # Would look up temple
    if not temple or not temple.is_holy_temple(priest) or not priest.mpeaceful:
        cranky_msgs = [
            "Thou wouldst have words, eh? I'll give thee a word or two!",
            "Talk? Here is what I have to say!",
            "Pilgrim, I would speak no longer with thee."
        ]
        print(f"{priest.name}: {cranky_msgs[random.randint(0, 2)]}")
        priest.mpeaceful = False
        return
    
    # Check for donation
    if player.invent_gold == 0:
        if coaligned and not strayed:
            pmoney = 10  # Simplified - priest's gold
            if pmoney > 0:
                print(f"{priest.name} gives you {'one ' if pmoney == 1 else ''}bits for an ale.")
                player.invent_gold += pmoney
        else:
            print(f"{priest.name} is not interested.")
        return
    
    # Donation handling
    suggested = player.ulevelpeak * random.randint(150, 250)
    quan = player.invent_gold // (suggested * 3)
    if quan < 1:
        quan = 1
    
    print(f"{priest.name} asks for a contribution (suggested: {suggested * quan} or {suggested * quan * 2}).")
    
    # Simplified bribery logic
    offer = random.randint(suggested * quan, suggested * quan * 3)
    if offer >= suggested * quan * 2:
        print(f"{priest.name} bestows a blessing upon thee!")
        player.ublessed += 1
        if coaligned and player.ualign_record <= ALGN_SINNED:
            player.ualign_record += 1
    else:
        print(f"{priest.name}: 'Cheapskate.'")


def angry_priest(room_id: str, temples: Dict[str, Temple]):
    """Make priest angry when temple is attacked"""
    temple = temples.get(room_id)
    if not temple or not temple.priest:
        return
    
    priest = temple.priest
    epri = priest.epri()
    
    # Check if shrine is still valid
    if not temple.has_shrine(priest):
        # Convert to roaming minion
        priest.ispriest = False
        if not priest.isminion:
            priest.set_minion_data(epri.shralign if epri else 0)
        priest.free_epri()
        print(f"{priest.name} loses their shrine and becomes a roaming zealot!")
    else:
        print(f"{priest.name} is angered by your actions!")
        priest.mpeaceful = False


def ghod_hitsu(priest: PriestMonster, temples: Dict[str, Temple]):
    """God strikes when attacking priest in temple"""
    room_id = temple_occupied(player.urooms)
    if not room_id:
        return
    
    temple = temples.get(room_id)
    if not temple or not temple.has_shrine(priest):
        return
    
    # God's wrath message
    messages = [
        f"Lightning strikes near you! '{priest.name}' roars in anger: 'Thou shalt suffer!'",
        f"A booming voice declares: 'How darest thou harm my servant!'",
        f"Lightning flashes as '{priest.name}' roars: 'Thou dost profane my shrine!'"
    ]
    print(random.choice(messages))
    
    # Apply damage effect (simplified)
    print("You take lightning damage!")


# --- Priest Creation ---

def create_priest(temple: Temple, x: int = 0, y: int = 0) -> PriestMonster:
    """Create a new priest for a temple"""
    priest = PriestMonster("Aligned Cleric", temple.alignment, x, y)
    epri = priest.epri()
    epri.shroom = temple.room_id
    epri.shralign = temple.alignment
    epri.shrpos = Coord(temple.shrine_pos.x, temple.shrine_pos.y)
    epri.shrlevel = temple.level
    
    temple.priest = priest
    temple.alignment = temple.alignment  # Align temple
    return priest


def create_roamer(name: str, align: int, x: int = 0, y: int = 0, peaceful: bool = True) -> RoamerMonster:
    """Create a roaming minion"""
    return RoamerMonster(name, align, x, y, peaceful)


# --- Utility Functions ---

def priestname(monster: Monster, article: int = 0, reveal_high: bool = False) -> str:
    """Get special name for aligned monster"""
    if monster.ispriest:
        name = "priestess" if getattr(monster, 'female', False) else "priest"
    elif monster.isminion:
        emin = monster.emin()
        if emin and emin.renegade:
            name = "renegade " + monster.name
        else:
            name = monster.name
    else:
        name = monster.name
    
    if article == 0:  # ARTICLE_THE
        return f"the {name}"
    return name


def in_your_sanctuary(monster: Monster, temples: Dict[str, Temple]) -> bool:
    """Check if in your sanctuary"""
    if player.ualign_record <= ALGN_SINNED:
        return False
    
    room_id = temple_occupied(player.urooms)
    if not room_id:
        return False
    
    priest = find_priest(room_id, temples)
    if not priest:
        return False
    
    temple = temples.get(room_id)
    if not temple:
        return False
    
    return (temple.has_shrine(priest) and 
            player.is_coaligned(priest) and 
            priest.mpeaceful)


# --- Example Usage ---

if __name__ == "__main__":
    # Create some temples
    temples = {
        "temple_1": Temple("temple_1", 10, 10),
        "temple_2": Temple("temple_2", 20, 20),  # Sanctum
    }
    
    # Set player alignment
    player.ualign_type = ALGN_LAWFUL
    player.invent_gold = 100
    
    # Create priests
    create_priest(temples["temple_1"], 10, 10)
    create_priest(temples["temple_2"], 20, 20)
    
    # Example interactions
    print("=== Temple Interaction ===")
    priest = temples["temple_1"].priest
    print(f"Found: {priestname(priest)}")
    print(f"Alignment: {'Lawful' if priest.get_alignment() == ALGN_LAWFUL else 'Chaotic'}")
    
    # Talk to priest
    priest_talk(priest)
    
    # Show sanctuary check
    print(f"\nIn sanctuary: {in_your_sanctuary(priest, temples)}")
    
    # Create roamer
    print("\n=== Roamer Interaction ===")
    roamer = create_roamer("Zealot", ALGN_LAWFUL, 15, 15, peaceful=False)
    print(f"Created: {priestname(roamer)}")
    print(f"Renegade: {roamer.emin().renegade if roamer.emin() else False}")
    
    # Reset hostility
    roamer.reset_hostility()
    print(f"Peaceful after reset: {roamer.mpeaceful}")

