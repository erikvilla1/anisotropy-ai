"""One entry point for a deck: the membrane kernel for the in-plane problems it was validated on, the flat shell kernel for everything
that bends (ADR-0029, ADR-0053). `fea/docs/theory.md`, Section 8."""

from __future__ import annotations

from .membrane import solve_membrane
from .model import Deck
from .results import MembraneSolution, ShellSolution, Solution
from .shell import needs_shell, solve_shell


def solve_deck(deck: Deck) -> Solution:
    """The shell kernel when the deck asks for bending, pressure, a load or a prescribed value on dofs 3 to 5, or an unsymmetric layup;
    the membrane kernel otherwise, so every in-plane result stays the one the committed cases and records pin."""
    return solve_shell(deck) if needs_shell(deck) else solve_membrane(deck)


def is_shell(solution: Solution) -> bool:
    return isinstance(solution, ShellSolution)


__all__ = ["MembraneSolution", "ShellSolution", "Solution", "is_shell", "needs_shell", "solve_deck"]
