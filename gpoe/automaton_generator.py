from collections import defaultdict
from itertools import product
from typing import Any

from gpoe.program import Function, Primitive, Program, Variable
from gpoe.tree_automaton import DFTA


def __type_split__(type_str: str) -> tuple[str, ...]:
    return tuple(map(lambda x: x.strip(), type_str.strip().split("->")))


__GRAMMARS__ = {}


def grammar_from_type_constraints(
    dsl: dict[str, tuple[str, callable]], requested_type: str
) -> DFTA[str, Program]:
    if requested_type not in __GRAMMARS__:
        req_type = __type_split__(requested_type)
        finals = set([req_type[-1]])
        rules: dict[tuple[Program, tuple[str, ...]], str] = {}
        # Add variables
        for i, state in enumerate(req_type[:-1]):
            rules[(Variable(i), tuple())] = state
        # Add elements from DSL
        for primitive, (str_type, fn) in dsl.items():
            btype = __type_split__(str_type)
            rtype = btype[-1]
            args = btype[:-1]
            rules[(Primitive(primitive), args)] = rtype

        dfta = DFTA(rules, finals)
        __GRAMMARS__[requested_type] = dfta
        return dfta
    else:
        return __GRAMMARS__[requested_type]


def grammar_from_type_constraints_and_commutativity(
    dsl: dict[str, tuple[str, callable]], requested_type: str, programs: list[Program]
) -> DFTA[str, Program]:
    req_type = __type_split__(requested_type)
    finals = set([req_type[-1]])
    rules: dict[tuple[Program, tuple[str, ...]], str] = {}
    prims_per_type = defaultdict(list)
    # Add variables
    for i, state in enumerate(req_type[:-1]):
        rules[(Variable(i), tuple())] = state
        if state not in prims_per_type[state]:
            prims_per_type[state].append(state)

    # Compute dict type -> primitives
    for primitive, (str_type, fn) in dsl.items():
        rtype = __type_split__(str_type)[-1]
        prims_per_type[rtype].append(primitive)
    # Add elements from DSL
    for primitive, (str_type, fn) in dsl.items():
        # check if this primitive is commutative
        btype = __type_split__(str_type)
        args = btype[:-1]
        rtype = btype[-1]
        if rtype == req_type[-1]:
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
    memory: dict[Any, dict[int, list[Program]]], type_req: str
) -> DFTA[str, Program]:
    rules = {}
    max_size = max(max(memory[state].keys()) for state in memory)
    args_type = __type_split__(type_req)[:-1]
    rtype = __type_split__(type_req)[-1]
    var_merge = {}
    var_merge_rev = {}
    for i, t in enumerate(args_type):
        if t in var_merge_rev:
            var_merge[i] = var_merge_rev[t]
        else:
            var_merge_rev[t] = i
            var_merge[i] = i
    finals = set()
    for size in range(1, max_size):
        for state in memory:
            programs = memory[state][size]
            for x in programs:
                x = __fix_vars__(x, var_merge)
                if isinstance(x, Function):
                    rules[(x.function, tuple(map(str, x.arguments)))] = str(x)
                else:
                    rules[(x, ())] = str(x)
                if state == rtype:
                    finals.add(str(x))

    dfta = DFTA(rules, finals)
    dfta.reduce()
    ndfta = dfta.minimise()
    mapping = {}

    def get_name(x) -> str:
        if x not in mapping:
            mapping[x] = f"S{len(mapping)}"
        return mapping[x]

    return ndfta.map_states(get_name)
