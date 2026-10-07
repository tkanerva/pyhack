"""Word inflection, ported directly from the original NetHack C.

This module is a faithful port of the word inflection code from the
original NetHack sources (see the NetHack tree, branch NetHack-5.0):

- ``makeplural()`` / ``makesingular()``   -- src/objnam.c
- ``s_suffix()`` / ``ing_suffix()``       -- src/hacklib.c

The previous implementation delegated these to the third-party
``inflect`` package.  That was a mistake: it added a dependency, and it
doesn't even implement everything the game needs -- there is no gerund
support at all (``ing_suffix``), and the plural/singular heuristics it
does have are generic English ones rather than the ones NetHack's text
actually relies on (item names, monster names, named fruits, body
parts).  The C code is small, self-contained, and tuned for exactly this
vocabulary, so porting it is the faithful option.

The port keeps the C *semantics* but not the C *plumbing*: no char
buffers, pointer bounds, or in-place overwrites -- just strings,
``str.endswith`` and a small case-pattern helper:

- Case preservation.  The C code writes replacements with
  ``strcasecpy()``, which gives each new character the case of the
  character it replaces, propagating the last old character's case
  once the old text runs out ("Knife" -> "Knives").  ``_case_swap()``
  / ``_match_case()`` do that on ordinary strings.
- Case-insensitive matching (strcmpi / strncmpi; makeplural() and
  makesingular() have been case-insensitive since 3.6.0) -> ``.lower()``
  comparisons.
- Compound names.  "potion of healing" pluralizes the head ("potions of
  healing"); ``_compound_cut()`` finds the split point.

The C originals return static / obuf buffers; the port returns fresh
strings, which is all the callers need.
"""
from __future__ import annotations

__all__ = ("ing_suffix", "makesingular", "makeplural", "s_suffix")

# vowels[] (decl.c) is "aeiouAEIOU"; every use site lowercases first.
_VOWELS = "aeiou"

# vowel[] in ing_suffix() (hacklib.c) -- note 'w' and 'y'.  Case-
# sensitive, exactly as in the C code.
_ING_VOWELS = "aeiouwy"

# genders[] (role.c) -- the entries makeplural()/makesingular() touch:
# (he, him, his) for male / female / neuter / group (plural).
_GENDERS = (
    ("he", "him", "his"),        # 0: male
    ("she", "her", "her"),       # 1: female
    ("it", "it", "its"),         # 2: neuter
    ("they", "them", "their"),   # 3: group (plural)
)

# already_plural[] -- makeplural() local in objnam.c: suffixes that are
# already plural and must not be touched.
_ALREADY_PLURAL = ("ae", "eaux", "matzot")

# as_is[] (objnam.c): words/suffixes left alone in both directions.
_AS_IS = (
    # makesingular() leaves these plural due to how they're used
    "boots", "shoes", "gloves", "lenses", "scales",
    "eyes", "gauntlets", "iron bars",
    # both singular and plural are spelled the same
    "bison", "deer", "elk", "fish", "fowl",
    "tuna", "yaki", "-hai", "krill", "manes",
    "moose", "ninja", "sheep", "ronin", "roshi",
    "shito", "tengu", "ki-rin", "Nazgul", "gunyoki",
    "piranha", "samurai", "shuriken", "haggis", "Bordeaux",
)

# one_off[] (objnam.c): irregular (singular, plural) word pairs.
_ONE_OFF = (
    ("child", "children"),      # (for wise guys who give their food funny names)
    ("cubus", "cubi"),          # in-/suc-cubus
    ("culus", "culi"),          # homunculus
    ("Cyclops", "Cyclopes"),
    ("djinni", "djinn"),
    ("erinys", "erinyes"),
    ("foot", "feet"),
    ("fungus", "fungi"),
    ("goose", "geese"),
    ("knife", "knives"),
    ("labrum", "labra"),        # candelabrum
    ("louse", "lice"),
    ("mouse", "mice"),
    ("mumak", "mumakil"),
    ("nemesis", "nemeses"),
    ("ovum", "ova"),
    ("ox", "oxen"),
    ("passerby", "passersby"),
    ("rtex", "rtices"),         # vortex
    ("serum", "sera"),
    ("staff", "staves"),
    ("tooth", "teeth"),
)

# special_subjs[] (objnam.c): various singular words that vtense would
# otherwise categorize as plural; also used by makesingular() to catch
# special cases.
_SPECIAL_SUBJS = (
    "erinys", "manes",  # this one is ambiguous
    "Cyclops", "Hippocrates", "Pelias", "aklys",
    "amnesia", "detect monsters", "paralysis", "shape changers",
    "nemesis",
)

# compounds[] (objnam.c): markers that split a compound name into the
# head (which gets inflected) and the rest.
_COMPOUNDS = (
    " of ", " labeled ", " called ", " named ", " above",
    " versus ", " from ", " in ", " on ", " a la ", " with",
    " de ", " d'", " du ", " au ", "-in-", "-at-",
)

# ch_k[] (objnam.c): some *ch words/suffixes that make a k-sound; they
# pluralize by adding 's' rather than 'es'.
_CH_K = (
    "monarch", "poch", "tech", "mech", "stomach", "psych",
    "amphibrach", "anarch", "atriarch", "azedarach", "broch",
    "gastrotrich", "isopach", "loch", "oligarch", "peritrich",
    "sandarach", "sumach", "symposiarch",
)

# badman() lists (objnam.c): prefixes for *man that don't have a *men
# plural, and for *men that don't have a *man singular.
_NO_MEN = (
    "albu", "antihu", "anti", "ata", "auto", "bildungsro", "cai", "cay",
    "ceru", "corner", "decu", "des", "dura", "fir", "hanu", "het",
    "infrahu", "inhu", "nonhu", "otto", "out", "prehu", "protohu",
    "subhu", "superhu", "talis", "unhu", "sha",
    "hu", "un", "le", "re", "so", "to", "at", "a",
)
_NO_MAN = (
    "abdo", "acu", "agno", "ceru", "cogno", "cycla", "fleh", "grava",
    "hegu", "preno", "sonar", "speci", "dai", "exa", "fla", "sta", "teg",
    "tegu", "vela", "da", "hy", "lu", "no", "nu", "ra", "ru", "se", "vi",
    "ya", "o", "a",
)


# ------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------

def _highc(c: str) -> str:
    """C highc(): force one character into uppercase."""
    return chr(ord(c) & ~0x40) if 'a' <= c <= 'z' else c


def _letter(c: str) -> bool:
    """C letter(): '@' through 'Z' and 'a' through 'z'.  '@' is a
    letter because inventory letters range @..z."""
    return '@' <= c <= 'Z' or 'a' <= c <= 'z'


def _isvowel(c: str) -> bool:
    """C strchr(vowels, lowc(c))."""
    return c.lower() in _VOWELS


def _match_case(ref: str, ch: str) -> str:
    """C chrcasecpy(): convert character ch into ref's case."""
    if 'a' <= ref <= 'z' and 'A' <= ch <= 'Z':
        return ch.lower()
    if 'A' <= ref <= 'Z' and 'a' <= ch <= 'z':
        return ch.upper()
    return ch


def _case_swap(old: str, new: str) -> str:
    """C strcasecpy() over a replaced range: return `new` rewritten with
    the case pattern of `old` -- each character of `new` takes the case
    of the character of `old` it replaces, and characters of `new` beyond
    the length of `old` take the case of `old`'s last character.  `old`
    must not be empty."""
    return ''.join(_match_case(old[i] if i < len(old) else old[-1], ch)
                   for i, ch in enumerate(new))


def _upstart_if(ref: str, res: str) -> str:
    """C idiom from makeplural()/makesingular():

        if (oldstr[0] == highc(oldstr[0]))
            str[0] = highc(str[0]);
    """
    if ref and res and ref[0] == _highc(ref[0]):
        return _highc(res[0]) + res[1:]
    return res


def _compound_cut(s: str):
    """C singplur_compound() (objnam.c): index of the first compound
    marker inside s (" of ", " labeled ", ...) or None."""
    for i, ch in enumerate(s):
        # substring starting at i can only match if ch is in the list of
        # first characters for all compounds[] entries (" -")
        if ch in ' -':
            low = s[i:].lower()
            for cmpd in _COMPOUNDS:
                if low.startswith(cmpd):
                    return i
    return None


def _ch_ksound(word: str) -> bool:
    """C ch_ksound() (objnam.c): does word end in one of the k-sounding
    *ch words/suffixes (pluralized by adding 's' rather than 'es')?"""
    return len(word) >= 4 and word.lower().endswith(_CH_K)


def _badman(word: str, to_plural: bool) -> bool:
    """C badman() (objnam.c): a *man word whose prefix says there is no
    *men plural (to_plural), or a *men word with no *man singular."""
    low = word.lower()
    if len(low) < 4:
        return False
    for pfx in (_NO_MEN if to_plural else _NO_MAN):
        al = len(pfx)
        spot = len(low) - al - 3
        if (spot >= 0 and low[spot:spot + al] == pfx
                and (spot == 0 or low[spot - 1] == ' ')):
            return True
    return False


def _singplur_lookup(word: str, to_plural: bool, alt_as_is):
    """C singplur_lookup() (objnam.c): singularize/pluralize decisions
    common to both makesingular() and makeplural().

    Returns the finished word when the word is (or has been made)
    correct as-is, or None when the formula-based rules should run.
    alt_as_is is "another set like as_is[]" (already_plural for
    makeplural, special_subjs for makesingular).
    """
    low = word.lower()

    for entry in _AS_IS:
        if low.endswith(entry.lower()):
            return word
    for entry in alt_as_is:
        if low.endswith(entry.lower()):
            return word

    # Leave "craft" as a suffix as-is (aircraft, hovercraft); "craft"
    # itself is (arguably) not included in our likely context
    if len(word) > 5 and low.endswith("craft"):
        return word

    # avoid false hit on one_off[].plur == "lice" or .sing == "goose"
    if low in ("slice", "mongoose"):
        # slice/mongoose: append s when pluralizing
        return word + _case_swap(word[-1], "s") if to_plural else word

    # skip "ox" -> "oxen" entry when pluralizing "<something>ox"
    # unless it is muskox
    if (to_plural and len(word) > 2 and low.endswith("ox")
            and not low.endswith("muskox")):
        return word + _case_swap(word[-1], "es")  # "fox" -> "foxes"

    if to_plural:
        if low.endswith("man") and _badman(word, True):
            return word + _case_swap(word[-1], "s")
    else:
        if low.endswith("men") and _badman(word, False):
            return word

    for sing, plur in _ONE_OFF:
        # check whether the word already matches the wanted form
        if low.endswith((plur if to_plural else sing).lower()):
            return word
        # check whether it matches the inverse; if so, transform it
        other = (sing if to_plural else plur).lower()
        if low.endswith(other):
            target = plur if to_plural else sing
            return word[:-len(other)] + _case_swap(word[-len(other):], target)
    return None


# ------------------------------------------------------------
# The four public functions
# ------------------------------------------------------------

def makeplural(s: str) -> str:
    """C makeplural() (objnam.c): pluralize a word, or the head of a
    compound name ("potion of healing" -> "potions of healing")."""
    s = s.lstrip(' ')
    if not s:
        return "s"  # C: impossible("plural of null?"); return "s"

    # makeplural() is sometimes used on monsters rather than objects and
    # sometimes pronouns are used for monsters, so check those;
    # unfortunately, "her" (which matches genders[1].him and [1].his) and
    # "it" (which matches genders[2].he and [2].him) are ambiguous;
    # we'll live with that; caller can fix things up if necessary.
    low = s.lower()
    for he, him, his in _GENDERS[:3]:
        if low == he:
            return _upstart_if(s, _GENDERS[3][0])   # "they"
        if low == him:
            return _upstart_if(s, _GENDERS[3][1])   # "them"
        if low == his:
            return _upstart_if(s, _GENDERS[3][2])   # "their"

    # Skip changing "pair of" to "pairs of".  According to Webster, usual
    # English usage is use pairs for humans and pair for objects and
    # non-humans; we don't refer to pairs of humans in this game so just
    # leave it alone.
    if low.startswith("pair of "):
        return s

    # look for "foo of bar" so that we can focus on "foo"
    cut = _compound_cut(s)
    head, excess = (s[:cut], s[cut:]) if cut is not None else (s, "")
    head = head.rstrip(' ')
    low = head.lower()

    # single letters (len <= 1 also covers the degenerate empty head that
    # C would read one byte past its buffer for -- UB over there, so we
    # just do the sensible thing here)
    if len(head) <= 1 or not _letter(head[-1]):
        return head + "'s" + excess

    # dispense with some words which don't need pluralization
    done = _singplur_lookup(head, True, _ALREADY_PLURAL)
    if done is not None:
        return done + excess
    # more of same, but not suitable for blanket loop checking
    if low == "ya" or low.endswith(" ya"):
        return head + excess

    # man/men ("Wiped out all cavemen.")
    if low.endswith("man") and not _badman(head, True):
        # exclude shamans and humans etc via badman()
        return head[:-2] + _case_swap(head[-2:], "en") + excess

    # [aeioulr]f to [aeioulr]ves (staff handled via one_off[])
    if low[-1] == 'f':
        if not low.endswith("erf") and (low[-2] in "lr"
                                        or _isvowel(low[-2])):
            # (avoid "nerf" -> "nerves", "serf" -> "serves")
            return head[:-1] + _case_swap(head[-1], "ves") + excess
        # else: fall through to default (append 's')

    # ium/ia (mycelia, baluchitheria)
    if low.endswith("ium"):
        return head[:-3] + _case_swap(head[-3:], "ia") + excess

    # algae, larvae, hyphae (another fungus part), amoebae, vertebrae
    if low.endswith(("alga", "hypha", "larva", "amoeba", "vertebra")):
        return head + _match_case(head[-1], 'e') + excess  # a to ae

    # fungus/fungi, homunculus/homunculi, but buses, lotuses, wumpuses
    if (len(head) > 3 and low.endswith("us")
            and not low.endswith(("lotus", "wumpus"))):
        return head[:-2] + _case_swap(head[-2:], "i") + excess

    # sis/ses (nemesis)
    if low.endswith("sis"):
        return head[:-2] + _case_swap(head[-2:], "es") + excess

    # -eau/-eaux (gateau, chapeau...)
    if low.endswith("eau") and not low.endswith("bureau"):
        # 'bureaus' is the more common plural of 'bureau'
        return head + _match_case(head[-1], 'x') + excess

    # matzoh/matzot, possible food name
    if low.endswith(("matzoh", "matzah")):
        return head[:-2] + _case_swap(head[-2:], "ot") + excess  # oh/ah -> ot
    if low.endswith(("matzo", "matza")):
        return head[:-1] + _case_swap(head[-1], "ot") + excess   # o/a -> ot

    # note: ox/oxen, VAX/VAXen, goose/geese (handled via lookup above)

    # codex/spadix/neocortex and the like
    if (len(head) >= 5 and low.endswith(("dex", "dix", "tex"))
            # indices would have been ok too, but stick with indexes
            and not low.endswith("index")):
        return head[:-2] + _case_swap(head[-2:], "ices") + excess  # ex|ix

    # Ends in z, x, s, ch, sh; add an "es"
    if (low[-1] in "zxs"
            or (low[-1] == 'h' and low[-2] in "cs"
                # 21st century k-sound
                and not (low[-2] == 'c' and _ch_ksound(head)))
            # Kludge to get "tomatoes" and "potatoes" right
            or (len(head) >= 4 and low.endswith("ato"))
            or low.endswith("dingo")):
        return head + _case_swap(head[-1], "es") + excess

    # Ends in y preceded by consonant (note: also "qu") change to "ies"
    if low[-1] == 'y' and not _isvowel(low[-2]):
        return head[:-1] + _case_swap(head[-1], "ies") + excess

    # Default: append an 's'
    return head + _case_swap(head[-1], "s") + excess


def makesingular(s: str) -> str:
    """C makesingular() (objnam.c): singularize a word the user typed in
    (or the head of a compound name)."""
    s = s.lstrip(' ')
    if not s:
        return ""  # C: impossible("singular of null?"); empty string

    # makeplural() of pronouns isn't reversible but at least we can
    # force a singular value
    low = s.lower()
    if low in _GENDERS[3]:
        # "they"/"them" -> "it"; "their" -> "its"
        return _upstart_if(s, "its" if low == _GENDERS[3][2] else "it")

    # check for "foo of bar" so that we can focus on "foo"
    cut = _compound_cut(s)
    head, excess = (s[:cut], s[cut:]) if cut is not None else (s, "")
    low = head.lower()

    # dispense with some words which don't need singularization
    done = _singplur_lookup(head, False, _SPECIAL_SUBJS)
    if done is not None:
        return done + excess

    # remove -s or -es (boxes) or -ies (rubies)
    if low.endswith("s"):
        if low.endswith("es"):
            if low.endswith("ies"):
                if (low.endswith("cookies")
                        or (low.endswith("pies")
                            # avoid false match for "harpies"
                            and (len(head) == 4 or head[-5] == ' '))
                        # alternate djinni/djinn spelling; not really needed
                        or (low.endswith("genies")
                            # avoid false match for "progenies"
                            and (len(head) == 6 or head[-7] == ' '))
                        or low.endswith("mbies")   # zombie
                        or low.endswith("yries")):  # valkyrie
                    return head[:-1] + excess
                return head[:-3] + _case_swap(head[-3:], "y") + excess
            # wolves, but f to ves isn't fully reversible
            if (len(head) >= 4
                    and (low[-4] in "lr" or _isvowel(low[-4]))
                    and not low.endswith("ves")):
                if low.endswith(("cloves", "nerves")):
                    return head[:-1] + excess
                return head[:-3] + _case_swap(head[-3:], "f") + excess
            # note: nurses, axes but boxes, wumpuses
            if low.endswith(("eses", "oxes", "nxes", "ches", "uses",
                             "shes", "sses", "atoes", "dingoes",
                             "aleaxes")):
                return head[:-2] + excess  # drop es
            return head[:-1] + excess      # drop s
        if low.endswith("us"):             # lotus, fungus...
            if not low.endswith(("tengus", "hezrous")):
                return head[:-1] + excess  # drop s
            return head + excess           # ...but not these
        if (low.endswith("ss")
                or low.endswith(" lens")
                or low == "lens"):
            return head + excess
        return head[:-1] + excess          # drop s

    # input doesn't end in 's'
    if low.endswith("men") and not _badman(head, False):
        return head[:-2] + _case_swap(head[-2:], "an") + excess  # men -> man
    # matzot -> matzo, algae -> alga
    if low.endswith(("matzot", "ae", "eaux")):
        return head[:-1] + excess          # drop t/e/x
    # balactheria -> balactherium
    if (len(head) >= 4 and low.endswith("ia")
            and low[-3] in "lr" and low[-4] == 'e'):
        return head[:-1] + _case_swap(head[-1], "um") + excess

    # here we cannot find the plural suffix
    return head + excess


def s_suffix(s: str) -> str:
    """C s_suffix() (hacklib.c): a name converted to the possessive.
    it -> its (not "it's"), you -> your, X -> X's, Xs -> Xs'."""
    low = s.lower()
    if low == "it":
        return s + "s"
    if low == "you":
        return s + "r"
    if s.endswith('s'):
        return s + "'"
    return s + "'s"


def ing_suffix(s: str) -> str:
    """C ing_suffix() (hacklib.c): construct a gerund (a verb formed by
    appending "ing").  tip -> "tipping", vie -> "vying", grease ->
    "greasing", "jump on" -> "jumping on"."""
    onoff = ""
    low = s.lower()
    if (len(s) >= 3 and low.endswith(" on")) \
            or (len(s) >= 4 and low.endswith(" off")) \
            or (len(s) >= 5 and low.endswith(" with")):
        sp = s.rfind(' ')
        onoff = s[sp:]
        s = s[:sp]
    low = s.lower()
    if low.endswith("er"):
        pass  # slither + ing
    elif (len(s) >= 3
          and s[-1] not in _ING_VOWELS
          and s[-2] in _ING_VOWELS
          and s[-3] not in _ING_VOWELS):
        s += s[-1]                    # tip -> tipp + ing
    elif low.endswith("ie"):
        s = s[:-2] + 'y'              # vie -> vy + ing
    elif s.endswith('e'):
        s = s[:-1]                    # grease -> greas + ing
    return s + "ing" + onoff
