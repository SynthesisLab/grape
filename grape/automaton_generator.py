from dataclasses import dataclass
from itertools import product
import sys
from typing import Any, Callable
from tqdm import tqdm

from grape.dsl import DSL
from grape.enumerator import Enumerator
from grape.program import Function, Primitive, Program, Variable
from grape.automaton.tree_automaton import DFTA
import grape.types as types


@dataclass
class Constraint:
    init: Callable
    transition: Callable
    """
    Returning None forbids the transition
    """
    is_final: Callable


def size_constraint(min_size: int = 0, max_size: int = -1) -> Constraint:
    def transition(p: Program, args: tuple[int, ...]) -> int | None:
        if any(x is None for x in args):
            return None
        if any(x == -1 for x in args):
            if max_size <= 0:
                return -1
            return None
        dst = 1 + sum(args)
        if max_size <= 0:
            return dst if dst < min_size else -1
        else:
            return dst if dst <= max_size else None

    return Constraint(
        lambda _: 1,
        transition,
        lambda s: s == -1 or (s >= min_size and (max_size > 0 and s <= max_size)),
    )


def depth_constraint(min_depth: int = 0, max_depth: int = -1) -> Constraint:
    def transition(p: Program, args: tuple[int, ...]) -> int | None:
        if any(x is None for x in args):
            return None
        if any(x == -1 for x in args):
            if max_depth <= 0:
                return -1
            return None
        dst = 1 + max(args)
        if max_depth <= 0:
            return dst if dst < min_depth else -1
        else:
            return dst if dst <= max_depth else None

    return Constraint(
        lambda _: 1,
        transition,
        lambda s: s == -1 or (s >= min_depth and (max_depth > 0 and s <= max_depth)),
    )


def commutativity_constraint(
    dsl: DSL, commutatives: list[tuple[str, list[int]]], type_req: str
) -> Constraint:
    arg_types, target_type = types.parse(type_req)
    to_check: dict[str, list[tuple[int, int]]] = {}
    for p, swapped in commutatives:
        if p not in to_check:
            to_check[p] = []
        to_check[p].append((swapped[0], swapped[1]))

    def transition(p: Program, args: tuple[str, ...]) -> str | None:
        if isinstance(p, Function):
            key = str(p.function)
            if key in to_check:
                if all(args[i] <= args[j] for i, j in to_check[key]):
                    return key
                else:
                    return None
            else:
                return key
        else:
            return str(p)

    return Constraint(
        str,
        transition,
        lambda s: target_type == "none"
        or (
            types.return_type(dsl.primitives[s][0]) == target_type
            if s in dsl.primitives
            else arg_types[int(s[len("var") :])]
        ),
    )


def grammar_by_saturation(
    dsl: DSL, requested_type: str, constraints: list[Constraint] = []
) -> DFTA[Any, Program]:
    args, rtype = types.parse(requested_type)
    whatever = rtype == "None"
    rules: dict[tuple[Program, tuple[str, ...]], str] = {}

    added = True
    states = set()
    finals = set()
    for i, var_type in enumerate(args):
        var = Variable(i)
        state = (var_type, tuple(c.init(var) for c in constraints))
        rules[(var, tuple())] = state
        if state not in states:
            states.add(state)
            added = True
            if (whatever or state[0] == rtype) and all(
                c.is_final(state[1][i]) for i, c in enumerate(constraints)
            ):
                finals.add(state)
    while added:
        added = False
        for primitive, (str_type, _) in dsl.primitives.items():
            arg_types = types.arguments(str_type)
            prog = Primitive(primitive)
            if len(arg_types) == 0:
                state = (
                    types.return_type(str_type),
                    tuple(c.init(prog) for c in constraints),
                )
                rules[(prog, tuple())] = state
                if state not in states:
                    states.add(state)
                    added = True
                    if (whatever or state[0] == rtype) and all(
                        c.is_final(state[1][i]) for i, c in enumerate(constraints)
                    ):
                        finals.add(state)
            else:
                possibles = [
                    [state for state in states if state[0] == arg_type]
                    for arg_type in arg_types
                ]
                for combination in product(*possibles):
                    key = (prog, combination)
                    if key in rules:
                        continue
                    dst_constraints = []
                    skip = False
                    for i, c in enumerate(constraints):
                        out = c.transition(
                            key[0], tuple(combi[1][i] for combi in combination)
                        )
                        skip = skip or out is None
                        dst_constraints.append(out)
                    if skip:
                        continue
                    dst = (types.return_type(str_type), tuple(dst_constraints))
                    if dst not in states:
                        states.add(dst)
                        added = True
                        if (whatever or dst[0] == rtype) and all(
                            c.is_final(dst[1][i]) for i, c in enumerate(constraints)
                        ):
                            finals.add(dst)
                    rules[key] = dst
    return DFTA(rules, finals)


def __fix_vars__(program: Program, var_merge: dict[int, int]) -> Program:
    if isinstance(program, Primitive):
        return program
    elif isinstance(program, Variable):
        return Variable(var_merge[program.no])
    elif isinstance(program, Function):
        return Function(
            __fix_vars__(program.function, var_merge),
            [__fix_vars__(arg, var_merge) for arg in program.arguments],
        )


def grammar_from_memory(
    memory: dict[Any, dict[int, list[Program]]],
    type_req: str,
    prev_finals: set[str],
) -> tuple[DFTA[str, Program], int]:
    max_size = max(max(memory[state].keys()) for state in memory)
    args_type = types.arguments(type_req)
    # Compute variable merging: all variables of same type should be merged
    var_merge = {}
    type2var = {}
    for i, t in enumerate(args_type):
        if t in type2var:
            var_merge[i] = type2var[t]
        else:
            type2var[t] = i
            var_merge[i] = i
    # Produce rules incrementally
    rules: dict[tuple[Program, tuple[str, ...]], str] = {}
    finals: set[str] = set()

    for size in tqdm(range(1, max_size + 1), desc="building automaton"):
        for state in sorted(memory):
            programs = memory[state][size]
            fixed = {__fix_vars__(prog, var_merge) for prog in programs}
            for prog in fixed:
                dst = str(prog)
                if isinstance(prog, Function):
                    key = (prog.function, tuple(map(str, prog.arguments)))
                else:
                    key = (prog, ())
                rules[key] = dst
                if state in prev_finals:
                    finals.add(dst)
    relevant_dfta = DFTA(rules, finals)

    # ==================================
    #  STATS
    # ==================================

    # Reproduce original type request to compare number of programs
    # add a rule for each deleted variable
    added = set()
    for i, j in var_merge.items():
        if i == j:
            continue
        # data: variable i is renamed as variable j
        old = Variable(i)
        for (prog, _), dst in relevant_dfta.rules.copy().items():
            if isinstance(prog, Variable) and prog.no == j:
                relevant_dfta.rules[(old, ())] = dst
                added.add((old, ()))
    relevant_dfta.refresh_reversed_rules()
    n = relevant_dfta.trees_until_size(max_size)
    # Delete them now that they have been used
    for x in added:
        del relevant_dfta.rules[x]
    relevant_dfta.refresh_reversed_rules()
    # ==================================

    return relevant_dfta, n
