from collections import defaultdict
from itertools import product
from typing import Any

from gpoe.program import Function, Primitive, Program, Variable
from gpoe.tree_automaton import DFTA
import gpoe.types as types


__GRAMMARS__ = {}


def grammar_from_type_constraints(
    dsl: dict[str, tuple[str, callable]], requested_type: str
) -> DFTA[str, Program]:
    if requested_type not in __GRAMMARS__:
        args, rtype = types.parse(requested_type)
        finals = set([rtype])
        rules: dict[tuple[Program, tuple[str, ...]], str] = {}
        # Add variables
        for i, state in enumerate(rtype):
            rules[(Variable(i), tuple())] = state
        # Add elements from DSL
        for primitive, (str_type, fn) in dsl.items():
            args, rtype = types.parse(str_type)
            rules[(Primitive(primitive), args)] = rtype

        dfta = DFTA(rules, finals)
        __GRAMMARS__[requested_type] = dfta
        return dfta
    else:
        return __GRAMMARS__[requested_type]


def grammar_from_type_constraints_and_commutativity(
    dsl: dict[str, tuple[str, callable]], requested_type: str, programs: list[Program]
) -> DFTA[str, Program]:
    gargs, grtype = types.parse(requested_type)
    finals = set([grtype])
    rules: dict[tuple[Program, tuple[str, ...]], str] = {}
    prims_per_type = defaultdict(list)
    # Add variables
    for i, state in enumerate(gargs):
        rules[(Variable(i), tuple())] = state
        if state not in prims_per_type[state]:
            prims_per_type[state].append(state)

    # Compute dict type -> primitives
    for primitive, (str_type, fn) in dsl.items():
        rtype = types.return_type(str_type)
        prims_per_type[rtype].append(primitive)
    # Add elements from DSL
    for primitive, (str_type, fn) in dsl.items():
        # check if this primitive is commutative
        args, rtype = types.parse(str_type)
        if rtype == grtype:
            finals.add(primitive)
        patterns = [
            tuple(
                [
                    args[el.no]
                    if isinstance(el, Variable)
                    else (str(el.function) if isinstance(el, Function) else str(el))
                    for el in p.arguments
                ]
            )
            for p in programs
            if isinstance(p, Function)
            and isinstance(p.function, Primitive)
            and p.function.name == primitive
        ]
        letter = Primitive(primitive)
        for nargs in product(*[prims_per_type[arg] for arg in args]):
            if nargs in patterns:
                continue
            rules[(letter, nargs)] = primitive

    dfta = DFTA(rules, finals)
    dfta.reduce()
    return dfta


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
    memory: dict[Any, dict[int, list[Program]]], type_req: str, prev_finals: set[str]
) -> DFTA[str, Program]:
    rules = {}
    max_size = max(max(memory[state].keys()) for state in memory)
    args_type = __type_split__(type_req)[:-1]
    # Compute variable merging: all variables of same type should be merged
    var_merge = {}
    var_merge_rev = {}
    for i, t in enumerate(args_type):
        if t in var_merge_rev:
            var_merge[i] = var_merge_rev[t]
        else:
            var_merge_rev[t] = i
            var_merge[i] = i
    # Produce rules incrementally
    finals = set()
    for size in range(1, max_size):
        for state in memory:
            programs = memory[state][size]
            for x in programs:
                x = __fix_vars__(x, var_merge)
                dst = str(x)
                if isinstance(x, Function):
                    rules[(x.function, tuple(map(str, x.arguments)))] = dst
                else:
                    rules[(x, ())] = dst
                if state in prev_finals:
                    finals.add(dst)

    dfta = DFTA(rules, finals)
    dfta.reduce()
    # return dfta

    ndfta = dfta.minimise()
    mapping = {}

    def get_name(x) -> str:
        if x not in mapping:
            mapping[x] = f"S{len(mapping)}"
        return mapping[x]

    return ndfta.map_states(get_name)
