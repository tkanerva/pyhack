"""Tests for the imperative shell (main.py).

The shell was the one path no test ran, and it is where `--mklev` broke:
`main()` built a single ``random.Random`` for every generator, so the
ported generators -- which draw through C's ``rn2`` / ``rnd`` / ``d``
(PLAN-MKLEV.md decision 8) -- raised
``'Random' object has no attribute 'rn2'`` inside makelevel, before the
first turn.  These tests run ``main()`` itself with the keyboard
scripted, so the whole loop (worldgen -> step -> events -> render) is
exercised for each generator; the console is the only thing faked.

The rng choice itself is pinned in tests/test_worldgen_generators.py
(``main.make_rng`` per generator); here the question is that the
program runs from `python main.py <flags>` to the last frame.
"""
import os
import sys

import pytest

import main as shell
from core.commands import MoveCommand, StairsCommand, WaitCommand


@pytest.fixture()
def play(monkeypatch):
    """Run `main()` with a key script instead of the keyboard.

    The screen-clear call is stubbed out so the captured output is the
    game text, not an escape sequence per turn.
    """
    def run(argv, commands):
        keys = list(commands)

        def read_command(world):
            return keys.pop(0) if keys else None

        monkeypatch.setattr(shell, "read_command", read_command)
        monkeypatch.setattr(os, "system", lambda command: 0)
        monkeypatch.setattr(sys, "argv", ["main.py"] + argv)
        shell.main()

    return run


@pytest.mark.parametrize("argv", [[], ["--mklev"], ["--cavern"]])
def test_main_plays_the_first_turns_on_every_generator(play, capsys, argv):
    """No argument is the pinned demo cave; --mklev and --cavern are the
    ported generators (the rng each one needs is make_rng's)."""
    play(argv, [MoveCommand(1, 0), MoveCommand(0, 1), WaitCommand(),
                StairsCommand(up=False)])
    out = capsys.readouterr().out
    assert "🎮 PyHack" in out
    assert "Level 1 of 3" in out, "the level renders"
    assert "@" in out, "the hero is on the screen"


def test_main_draws_the_last_frame_when_the_input_ends(play, capsys):
    """`Q` (here: the end of the script) leaves the loop and still draws
    the final frame plus the epilogue, as the demo always has."""
    play([], [])
    out = capsys.readouterr().out
    assert out.count("Level 1 of 3") >= 2, "the world screen and the exit"
    assert ("You survive the cave" in out or "Thanks for playing" in out)
