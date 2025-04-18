from collections import defaultdict
from dataclasses import dataclass
from itertools import product
import sys
from typing import Any
from tqdm import tqdm

from grape.automaton.loop_manager import LoopStrategy, add_loops
from grape.dsl import DSL
from grape.enumerator import Enumerator
from grape.program import Function, Primitive, Program, Variable
from grape.automaton.tree_automaton import DFTA
import grape.types as types


@dataclass
class Constraint:
    init: callable
    transition: callable
    is_final: callable


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


def grammar_from_type_constraints_and_commutativity(
    dsl: DSL, requested_type: str, programs: list[Program]
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
    for primitive, (str_type, fn) in dsl.primitives.items():
        rtype = types.return_type(str_type)
        prims_per_type[rtype].append(primitive)
    # Add elements from DSL
    for primitive, (str_type, fn) in dsl.primitives.items():
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
    dsl: DSL,
    memory: dict[Any, dict[int, list[Program]]],
    type_req: str,
    prev_finals: set[str],
    no_loop: bool = False,
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
    prod_programs: dict[int, dict[str, set[Program]]] = defaultdict(
        lambda: defaultdict(set)
    )
    consumed: set[Program] = set()
    state2type: dict[str, str] = {}

    def get_rtype(p: Program) -> str:
        if isinstance(p, Variable):
            return args_type[p.no]
        elif isinstance(p, Primitive):
            return dsl.primitives[p.name][0]
        elif isinstance(p, Function):
            return types.return_type(dsl.primitives[str(p.function)][0])
        else:
            raise ValueError

    for size in tqdm(range(1, max_size + 1), desc="building automaton"):
        for state in sorted(memory):
            programs = memory[state][size]
            fixed = {__fix_vars__(prog, var_merge) for prog in programs}
            for prog in fixed:
                dst = str(prog)
                if isinstance(prog, Function):
                    key = (prog.function, tuple(map(str, prog.arguments)))
                    if not no_loop:
                        consumed.update(prog.arguments)
                else:
                    key = (prog, ())
                assert key not in rules
                rules[key] = dst
                rtype = get_rtype(prog)
                state2type[dst] = rtype
                if not no_loop:
                    prod_programs[size][rtype].add(prog)
                if state in prev_finals:
                    finals.add(dst)
    relevant_dfta = add_loops(
        DFTA(rules, finals),
        dsl,
        LoopStrategy.NO_LOOP if no_loop else LoopStrategy.STATE,
        type_req,
    )
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
    n = relevant_dfta.trees_until_size(max_size)
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
    pbar = tqdm(total=dfta.trees_until_size(max_size), desc="checking")
    next(gen)
    size = 0
    count = 0
    while True:
        try:
            gen.send(True)
            count += 1
            if count & 15 == 0:
                pbar.update(16)
                count = 0
        except StopIteration:
            break
    pbar.update(count)
    pbar.close()
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
