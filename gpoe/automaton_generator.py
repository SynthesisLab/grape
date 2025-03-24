from collections import defaultdict
from itertools import product
import sys
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
        whatever = rtype == "None"
        finals = set([rtype]) if not whatever else set()
        rules: dict[tuple[Program, tuple[str, ...]], str] = {}
        # Add variables
        for i, state in enumerate(args):
            rules[(Variable(i), tuple())] = state
        # Add elements from DSL
        for primitive, (str_type, fn) in dsl.items():
            args, rtype = types.parse(str_type)
            if whatever:
                finals.add(rtype)
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
    whatever = grtype == "None"
    finals = set([grtype]) if not whatever else set()
    rules: dict[tuple[Program, tuple[str, ...]], str] = {}
    prims_per_type = defaultdict(list)
    # Add variables
    for i, state in enumerate(gargs):
        if whatever:
            finals.add(state)
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
        if rtype == grtype or whatever:
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
    memory: dict[Any, dict[int, list[Program]]],
    type_req: str,
    prev_finals: set[str],
    optimize: bool = False,
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
    prod_programs: dict[int, set[Program]] = defaultdict(set)
    consumed: set[Program] = set()
    for size in tqdm(range(1, max_size + 1), desc="building automaton"):
        for state in sorted(memory):
            programs = memory[state][size]
            fixed = {__fix_vars__(prog, var_merge) for prog in programs}
            for prog in fixed:
                dst = str(prog)
                prod_programs[size].add(prog)
                if isinstance(prog, Function):
                    key = (prog.function, tuple(map(str, prog.arguments)))
                    consumed.update(prog.arguments)
                else:
                    key = (prog, ())
                assert key not in rules
                rules[key] = dst
                if state in prev_finals:
                    finals.add(dst)

    # "Collapse" it to generate infinite size
    # 1. find all states which are not consumed
    not_consumed: set[Program] = set()
    for progs in sorted(prod_programs.values()):
        for prog in progs:
            if prog not in consumed:
                not_consumed.add(prog)
    # 2. Say that all not consumed must be consumed at some point
    # Assume they must be from some function
    state_collapse = {}

    # Used for optimize=True Flag
    # Compute the number of out derivations from given state
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

    for p in tqdm(not_consumed, desc="extending automaton"):
        # We should merge their state with the state of the highest sketch match
        merge_candidates = []
        size_of_canditates = 0
        best = float("inf")
        for csize in reversed(range(1, p.size())):
            if csize < size_of_canditates:
                break
            for prog in prod_programs[csize]:
                if (
                    prog != p
                    and (not optimize or compute_out(str(prog)) < best)
                    and prog.can_be_embed_into(p)
                ):
                    merge_candidates.append(prog)
                    best = (not optimize) or compute_out(str(prog))
                    break
        target = merge_candidates.pop(0)
        state_collapse[str(p)] = str(target)

    dfta = DFTA(rules, finals)
    dfta = dfta.map_states(lambda x: state_collapse.get(x, x))
    dfta.reduce()
    # Note: it is useless to minimise the automaton is already minimal
    mapping = {}

    def get_name(x: str) -> str:
        if x not in mapping:
            mapping[x] = f"S{len(mapping)}"
        return mapping[x]

    relevant_dfta = dfta.minimise().map_states(get_name)
    # free memory
    del dfta
    n = 0

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
    n = sum(relevant_dfta.trees_by_size(max_size).values())
    from_enum = test(memory, relevant_dfta, max_size)
    total_programs = sum(
        sum(len(memory[state][s]) for state in memory) for s in range(1, max_size + 1)
    )
    print(
        f"obs. equivalence: {total_programs:.3e} pruned: {from_enum:.3e} ({from_enum / total_programs:.2%})"
    )
    # Delete them now that they have been used
    for x in added:
        del relevant_dfta.rules[x]
    relevant_dfta.refresh_reversed_rules()

    return relevant_dfta, n


def test(
    memory: dict[Any, dict[int, list[Program]]], dfta: DFTA[Any, Program], max_size: int
) -> int:
    enum = Enumerator(dfta)
    gen = enum.enumerate_until_size(max_size + 1)
    pbar = tqdm(total=max_size, desc="checking")
    next(gen)
    size = 0
    while True:
        try:
            gen.send(True)
            if enum.current_size > size:
                size += 1
                pbar.update()
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
            total += len(programs)
    for value in memory.values():
        for size, programs in value.items():
            if size not in old_memory_to_size:
                old_memory_to_size[size] = []
            old_memory_to_size[size] += programs

    sizes = set(new_memory_to_size.keys()) | set(old_memory_to_size.keys())
    for size in sizes:
        if size not in new_memory_to_size:
            print(f"[warning] missing expressions of size: {size}", file=sys.stderr)
            print("[warning] stopped check here to avoid blow up", file=sys.stderr)
            break
        elif size not in old_memory_to_size:
            pass
            # print("+", new_memory_to_size[size])
        else:
            # more = set(new_memory_to_size[size]) - set(old_memory_to_size[size])
            less = set(old_memory_to_size[size]) - set(new_memory_to_size[size])
            # if more:
            #     print("+", more)
            if less:
                print(
                    f"[warning] missing the following of size {size}: {less}",
                    file=sys.stderr,
                )
                print("[warning] stopped check here to avoid blow up", file=sys.stderr)
                break
    return total
