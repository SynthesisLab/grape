from typing import Any
from gpoe.evaluator import Evaluator
from gpoe.program import Program
from gpoe.tree_automaton import DFTA


def find_approximate_constraints(
    dsl: dict[str, tuple[str, callable]],
    evaluator: Evaluator,
) -> list[tuple[Program, Program]]:
    return []


def __find_commutativity__(dsl: dict[str, tuple[str, callable]]):
    pass
