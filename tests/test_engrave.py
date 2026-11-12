"""Tests for the minimal engraving model (core.engrave) -- the create /
look-up / delete half of the NetHack engraving system that the swamp
pools (del_engr_at) and the shop door sign (make_engr_at) need.

What must hold: make_engr_at writes the text + tool type on the Tile
(the C head_engr list keyed by (x, y) becomes the Tile.engr field),
engr_at reads it back, del_engr_at clears it, make_engr_at replaces an
existing engraving, and out-of-bounds squares are refused (no write,
no crash).
"""

from core import engrave
from core.mklev import blank_map
from core.types import Engraving

W, H = 40, 20


def test_make_engr_at_writes_text_and_type():
    m = blank_map(W, H)
    engraving = engrave.make_engr_at(m, 5, 5, "Elbereth", engrave.E_STYLUS)
    assert isinstance(engraving, Engraving)
    assert engraving.text == "Elbereth"
    assert engraving.type == engrave.E_STYLUS
    # it is on the tile (the C (engr_x, engr_y) key becomes the Tile)
    assert m.tile_at((5, 5)).engr is engraving


def test_engr_at_reads_back_and_none_elsewhere():
    m = blank_map(W, H)
    engrave.make_engr_at(m, 5, 5, "no trespassing")
    assert m.tile_at((5, 5)).engr is not None
    assert engrave.engr_at(m, 5, 5).text == "no trespassing"
    # a neighbouring square has no engraving
    assert engrave.engr_at(m, 6, 5) is None


def test_del_engr_at_clears_the_square():
    m = blank_map(W, H)
    engrave.make_engr_at(m, 5, 5, "Elbereth")
    assert engrave.engr_at(m, 5, 5) is not None
    engrave.del_engr_at(m, 5, 5)
    assert engrave.engr_at(m, 5, 5) is None
    # deleting an empty square is a no-op (C: the if (ep) guard)
    engrave.del_engr_at(m, 5, 5)
    assert engrave.engr_at(m, 5, 5) is None


def test_make_engr_at_replaces_the_existing_one():
    m = blank_map(W, H)
    engrave.make_engr_at(m, 5, 5, "old", engrave.E_PEN)
    engrave.make_engr_at(m, 5, 5, "new", engrave.E_SABER)
    assert m.tile_at((5, 5)).engr.text == "new"
    assert m.tile_at((5, 5)).engr.type == engrave.E_SABER


def test_out_of_bounds_is_refused():
    m = blank_map(W, H)
    assert engrave.make_engr_at(m, W, 0, "nope") is None
    assert engrave.engr_at(m, W, 0) is None
    engrave.del_engr_at(m, W, 0)  # a no-op, no crash
    assert m.tile_at((W - 1, 0)).engr is None
