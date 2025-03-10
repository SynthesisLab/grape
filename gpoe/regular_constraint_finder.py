from collections import defaultdict
from gpoe.enumerator import Enumerator
from gpoe.evaluator import Evaluator
from gpoe.program import Program
from gpoe.automaton_generator import (
    grammar_from_memory,
    grammar_from_type_constraints_and_commutativity,
)
from gpoe.tree_automaton import DFTA

from tqdm import tqdm


def __type_split__(type_str: str) -> tuple[str, ...]:
    return tuple(map(lambda x: x.strip(), type_str.strip().split("->")))


def __infer_mega_type_req__(dsl: dict[str, tuple[str, callable]], rtype: str) -> str:
    # Capture max number of args of type that each type request needs
    use_all = defaultdict(int)
    for str_type, _ in dsl.values():
        args = __type_split__(str_type)[:-1]
        for t in args:
            n = sum(t == a for a in args)
            use_all[t] = max(use_all[t], n)
    # Produce the number of args
    univ_type_req = []
    for t, n in use_all.items():
        univ_type_req += [t] * n

    type_req = "->".join(univ_type_req + [rtype])
    return type_req


def find_regular_constraints(
    dsl: dict[str, tuple[str, callable]],
    evaluator: Evaluator,
    max_size: int,
    rtype: str,
    approx_constraints: list[tuple[Program, Program, str]],
) -> tuple[DFTA[str, Program], list[tuple[Program, Program, str]]]:
    constraints = []
    # Find all type requests
    type_req = __infer_mega_type_req__(dsl, rtype)

    grammar = grammar_from_type_constraints_and_commutativity(
        dsl, type_req, [p[0] for p in approx_constraints]
    )
    enumerator = Enumerator(grammar)
    # Generate all programs until some size
    pbar = tqdm(total=max_size + 1)
    pbar.set_description_str("regular constraints")
    gen = enumerator.enumerate_until_size(max_size + 1)
    program = next(gen)
    evaluator.eval(program, type_req)
    should_keep = True
    try:
        last_size = 1
        while True:
            program = gen.send(should_keep)
            same_used, var_used = program.same_var_used_more_than_once()
            if same_used:
                should_keep = False
            # elif 0 not in var_used or len(var_used) != nargs:
            # should_keep = True
            else:
                representative = evaluator.eval(program, type_req)
                should_keep = representative is None
                if not should_keep:
                    constraints.append((program, representative, type_req))
            if last_size < enumerator.current_size:
                pbar.update()
                last_size = enumerator.current_size
    except StopIteration:
        pass
    pbar.update()
    pbar.close()
    return grammar_from_memory(enumerator.memory, type_req), constraints
