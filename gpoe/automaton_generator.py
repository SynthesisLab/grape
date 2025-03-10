from itertools import product
from typing import Any

import tqdm
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
        dfta.reduce()
        __GRAMMARS__[requested_type] = dfta
        return dfta
    else:
        return __GRAMMARS__[requested_type]


def __tree_combine_on_letter__(
    letter: Program, args: list[DFTA[str, Program]]
) -> DFTA[str, Program]:
    # IDEA is easy
    # run all args in parallel
    # Then add a transition which maps correcly things
    args_cpy = [x for x in args]
    base = args_cpy.pop()
    while args_cpy:
        base = base.read_union(
            args_cpy.pop(), lambda x, y: (*x, y) if isinstance(x, tuple) else (x, y)
        )
    # base now reads all of them in parallel
    if len(args) == 1:
        matching = [[] for _ in args]
        for state in base.finals:
            for arg in args:
                if state in arg.finals:
                    matching[0].append(state)
        final = "win"
        while final in base.states:
            final += "1"
    else:
        matching = [[] for _ in args]
        for state in base.finals:
            for i, arg in enumerate(args):
                if state[i] in arg.finals:
                    matching[i].append(state)
        w = "win"
        final = tuple([w for _ in args])
        while final in base.states:
            w += "1"
            final = tuple([w for _ in args])
    for combinations in product(*matching):
        base.rules[(letter, combinations)] = final
    base.finals = {final}
    # if len(args) > 1:
    #     base = base.map_states(lambda t: " x ".join(t) if t is not None else "")
    return base


def __grammar_for_program__(
    dsl: dict[str, tuple[str, callable]], program: Program, type_req: str
) -> DFTA[str, Program]:
    if isinstance(program, Variable):
        args = list(map(lambda x: x.strip(), type_req.split("->")))
        vtype = args[program.no]
        args[-1] = vtype
        return grammar_from_type_constraints(dsl, "->".join(args))
    elif isinstance(program, Primitive):
        rtype = dsl[program.name][0]
        return DFTA({(program, tuple()): rtype}, {rtype})
    elif isinstance(program, Function):
        letter = program.function
        args_dfta = [
            __grammar_for_program__(dsl, arg, type_req) for arg in program.arguments
        ]
        return __tree_combine_on_letter__(letter, args_dfta)


def grammar_from_constraints(
    dsl: dict[str, tuple[str, callable]],
    constraints: list[tuple[Program, Program, str]],
) -> DFTA[str, Program]:
    p = constraints.pop()
    base = __grammar_for_program__(dsl, p[0], p[-1])
    for deleted, _, type_req in tqdm.tqdm(constraints, desc="compilation"):
        base = base.read_union(__grammar_for_program__(dsl, deleted, type_req))
        base = base.minimise()
    # base = base.complement()
    minim = base.minimise()
    mapping = {}

    def get_name(x) -> int:
        if x not in mapping:
            mapping[x] = f"S{len(mapping)}"
        return mapping[x]

    return minim.map_states(get_name)
