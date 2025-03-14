from collections import defaultdict
from itertools import product
from typing import Any
from tqdm import tqdm

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


def grammar_from_memory(
    dsl: dict[str, tuple[str, callable]],
    memory: dict[Any, dict[int, list[Program]]],
    type_req: str,
    prev_finals: set[str],
    keep_type_req: bool,
) -> tuple[DFTA[str, Program], int]:
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
        for state in sorted(memory):
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
    for state in sorted(prod_states):
        if all(state not in consumed for _, consumed in rules.keys()):
            not_consumed.add(state)
    # 2. Say that all not consumed must be consumed at some point
    # Assume they must be from some function
    state_collapse = {}
    prod_progs = [Program.parse(other) for other in sorted(prod_states)]
    progs_by_size: dict[int, list[Program]] = {size: [] for size in range(max_size + 1)}
    for p in prod_progs:
        progs_by_size[p.size()].append(p)

    out_transitions = {}

    def compute_out(state: str) -> int:
        if state not in out_transitions:
            n = 0
            for (letter, args), dst in rules.items():
                if any(arg == state for arg in args):
                    n += compute_out(dst)
            if n == 0:
                n = 1
            out_transitions[state] = n

        return out_transitions[state]

    for state in tqdm(not_consumed, desc="extending automaton"):
        # GABRIEL VERSION
        # for (letter, args) in rev_rules[state]:
        #     possibles = [[s for s in not_consumed_as_progs if arg.can_be_embed_into(s)] + [arg] for arg in args]
        #     for new_args in product(*possibles):
        #         rules_gab[(letter, tuple(map(str, new_args)))] = dst

        # We should merge their state with the state of the highest sketch match
        # THEO VERSION
        p = Program.parse(state)
        merge_candidates = []
        size_of_canditates = 0
        best = float("inf")
        for csize in reversed(range(1, p.size())):
            if csize < size_of_canditates:
                break
            for prog in progs_by_size[csize]:
                if (
                    prog != p
                    and compute_out(str(prog)) < best
                    and prog.can_be_embed_into(p)
                ):
                    merge_candidates.append(prog)
                    best = compute_out(str(prog))
        target = merge_candidates.pop(0)
        state_collapse[state] = str(target)

    dfta = DFTA(rules, finals)
    dfta = dfta.map_states(lambda x: state_collapse.get(x, x))
    dfta.reduce()
    # Note: it is useless to minimise the automaton is already minimal
    mapping = {}

    def get_name(x: str) -> str:
        if x not in mapping:
            mapping[x] = f"S{len(mapping)}"
        return mapping[x]

    relevant_dfta = dfta.map_states(get_name)
    n = 0

    # TO COUNT TREES YOU NEED TO RE ADD OTHER VARIABLES
    if keep_type_req:
        added = set()
        for i, j in var_merge.items():
            old = Variable(i)
            for (prog, _), dst in relevant_dfta.rules.copy().items():
                if isinstance(prog, Variable) and prog.no == j:
                    relevant_dfta.rules[(old, ())] = dst
                    added.add((old, ()))

        relevant_dfta.refresh_reversed_rules()
        n = relevant_dfta.trees_at_size(max_size)
        print(
            "memory:",
            total_programs,
            "dfta:",
            n,
        )
        for x in added:
            del relevant_dfta.rules[x]
        relevant_dfta.refresh_reversed_rules()

        # test(memory, relevant_dfta, max_size)
    return relevant_dfta, n


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
    total = 0
    for value in enum.memory.values():
        for size, programs in value.items():
            if size not in new_memory_to_size:
                new_memory_to_size[size] = []
            new_memory_to_size[size] += programs
            if size == max_size:
                total += len(programs)
    for value in memory.values():
        for size, programs in value.items():
            if size not in old_memory_to_size:
                old_memory_to_size[size] = []
            old_memory_to_size[size] += programs

    sizes = set(new_memory_to_size.keys()) | set(old_memory_to_size.keys())
    print("from enumeration:", total)
    for size in sizes:
        if size not in new_memory_to_size:
            assert False
        elif size not in old_memory_to_size:
            pass
        # print("+", new_memory_to_size[size])
        else:
            # more = set(new_memory_to_size[size]) - set(old_memory_to_size[size])
            less = set(old_memory_to_size[size]) - set(new_memory_to_size[size])
            # if more:
            # print("+", more)
            if less:
                assert False
