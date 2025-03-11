from collections import defaultdict
from itertools import product
from typing import Any

from gpoe.enumerator import Enumerator
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
        for i, state in enumerate(args):
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


def __get_args__(program: str) -> tuple[list[str], int]:
    elements = program.split(" ")
    first_level = []
    level = 0
    depth = 0
    for el in elements:
        if ")" in elements:
            level -= 1
        elif ")" in elements:
            level += 1
            depth = max(level, depth)
        if level == 0:
            first_level.append(el.strip("() "))
    return first_level, depth


def grammar_from_memory(
    dsl: dict[str, tuple[str, callable]],
    memory: dict[Any, dict[int, list[Program]]],
    type_req: str,
    prev_finals: set[str],
    keep_type_req: bool,
) -> DFTA[str, Program]:
    rules: dict[tuple[Program, tuple[str, ...]], str] = {}
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
    total_programs = sum(len(memory[state][max_size]) for state in memory)
    finals: set[str] = set()
    prod_states: set[str] = set()
    for size in range(1, max_size + 1):
        for state in memory:
            programs = memory[state][size]
            for x in programs:
                x = __fix_vars__(x, var_merge)
                dst = str(x)
                prod_states.add(dst)
                if isinstance(x, Function):
                    rules[(x.function, tuple(map(str, x.arguments)))] = dst
                else:
                    rules[(x, ())] = dst
                if state in prev_finals:
                    finals.add(dst)

    # "Collapse" it to generate infinite size
    # 1. find all states which are not consumed
    not_consumed: set[str] = set()
    for state in prod_states:
        if all(state not in consumed for _, consumed in rules.keys()):
            not_consumed.add(state)
    # 2. Say that all not consumed must be consumed at some point
    # Assume they must be from some function
    state_collapse = {}
    for state in not_consumed:
        primitive = state[1 : state.find(" ")]
        rtype = types.return_type(dsl[primitive][0])
        # We should merge their state with the state of the highest sketch match
        # But too hard so TODO
        # instead redirect them to first level things
        # args, depth = __get_args__(state[state.find(" ") + 1 : -1])
        #     print("\tstate:", state, "args:", args, "depth:", depth)
        # if depth == 0:
        target = Variable(type2var[rtype])
        state_collapse[state] = str(target)
        # else:
        #     pass
    dfta = DFTA(rules, finals)
    dfta = dfta.map_states(lambda x: state_collapse.get(x, x))
    dfta.reduce()
    ndfta = dfta.minimise()
    mapping = {}

    def get_name(x) -> str:
        if x not in mapping:
            mapping[x] = f"S{len(mapping)}"
        return mapping[x]

    relevant_dfta = ndfta.map_states(get_name)

    # TO COUNT TREES YOU NEED TO RE ADD OTHER VARIABLES
    if keep_type_req:
        for i, j in var_merge.items():
            old = Variable(i)
            dfta.rules[(old, ())] = str(Variable(j)).strip()
            for (prog, _), dst in relevant_dfta.rules.copy().items():
                if isinstance(prog, Variable) and prog.no == j:
                    relevant_dfta.rules[(old, ())] = dst

        dfta.refresh_reversed_rules()
        relevant_dfta.refresh_reversed_rules()
        print(
            "memory:",
            total_programs,
            "dfta:",
            dfta.trees_at_size(max_size),
            "ndfta:",
            relevant_dfta.trees_at_size(max_size),
        )

        # test(memory, relevant_dfta, max_size)
    return relevant_dfta


def test(memory, dfta, max_size):
    enum = Enumerator(dfta)
    gen = enum.enumerate_until_size(max_size + 1)
    next(gen)
    while True:
        try:
            gen.send(True)
        except StopIteration:
            break

    new_memory_to_size = {}
    old_memory_to_size = {}
    for value in enum.memory.values():
        for size, programs in value.items():
            if size not in new_memory_to_size:
                new_memory_to_size[size] = []
            new_memory_to_size[size] += programs
    for value in memory.values():
        for size, programs in value.items():
            if size not in old_memory_to_size:
                old_memory_to_size[size] = []
            old_memory_to_size[size] += programs

    sizes = set(new_memory_to_size.keys()) | set(old_memory_to_size.keys())

    for size in sizes:
        if size not in new_memory_to_size:
            assert False
        # elif size not in old_memory_to_size:
        # print("+", new_memory_to_size[size])
        else:
            # more = set(new_memory_to_size[size]) - set(old_memory_to_size[size])
            less = set(old_memory_to_size[size]) - set(new_memory_to_size[size])
            # if more:
            # print("+", more)
            if less:
                assert False
