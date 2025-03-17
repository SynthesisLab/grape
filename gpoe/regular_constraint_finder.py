from collections import defaultdict
from gpoe.enumerator import Enumerator
from gpoe.evaluator import Evaluator
from gpoe.program import Program
from gpoe.automaton_generator import (
    grammar_from_memory,
    grammar_from_type_constraints,
    grammar_from_type_constraints_and_commutativity,
)
from gpoe.tree_automaton import DFTA
import gpoe.types as types

from tqdm import tqdm


def __infer_mega_type_req__(
    dsl: dict[str, tuple[str, callable]], rtype: str, max_size: int
) -> str:
    # Capture max number of args of type that each type request needs
    max_arity_per_type = defaultdict(int)
    for str_type, _ in dsl.values():
        args = types.arguments(str_type)
        for arg in args:
            max_arity_per_type[arg] = max(max_arity_per_type[arg], len(args))
    # Produce the number of args
    univ_type_req = []
    for t, n in max_arity_per_type.items():
        j = int(max_size / 2 * (n - 1) + 1)
        univ_type_req += [t] * j

    type_req = "->".join(univ_type_req + [rtype])
    return type_req


def find_regular_constraints(
    dsl: dict[str, tuple[str, callable]],
    evaluator: Evaluator,
    max_size: int,
    rtype: str,
    approx_constraints: list[tuple[Program, Program, str]],
    optimize: bool = False,
) -> tuple[DFTA[str, Program], list[tuple[Program, Program, str]]]:
    constraints = []
    # Find all type requests
    type_req = __infer_mega_type_req__(dsl, rtype, max_size)

    base_grammar = grammar_from_type_constraints(dsl, type_req)
    grammar = grammar_from_type_constraints_and_commutativity(
        dsl, type_req, [p[0] for p in approx_constraints]
    )
    ntrees = sum(grammar.trees_by_size(max_size).values())
    basen = sum(base_grammar.trees_by_size(max_size).values())
    print("at size:", max_size)
    print(f"\tno pruning: {basen:.2e}")
    print(f"\tcommutativity pruned: {ntrees:.2e} ({ntrees / basen:.2%})")
    assert basen >= ntrees
    enumerator = Enumerator(grammar)
    # Generate all programs until some size
    pbar = tqdm(total=max_size)
    # target_size = max(len(types.arguments(t)) for t, _ in dsl.values()) + 1
    pbar.set_description_str("regular constraints")
    gen = enumerator.enumerate_until_size(max_size + 1)
    program = next(gen)
    evaluator.eval(program, type_req)
    should_keep = True
    try:
        last_size = 1
        while True:
            program = gen.send(should_keep)
            representative = evaluator.eval(program, type_req)
            should_keep = representative is None
            if not should_keep:
                constraints.append((program, representative, type_req))
            if last_size < enumerator.current_size:
                pbar.update()
                last_size = enumerator.current_size
                pbar.set_postfix_str(f"{len(constraints)}")
    except StopIteration:
        pass
    pbar.set_postfix_str(f"{len(constraints)}")
    pbar.update()
    pbar.close()
    reduced_grammar, t = grammar_from_memory(
        enumerator.memory, type_req, grammar.finals, optimize
    )
    print("at size:", max_size)
    print(
        "\tmethod: ratio no pruning | ratio comm. pruned | ratio pruned",
    )
    for n, v in [
        ("no pruning", basen),
        ("commutativity pruned", ntrees),
        ("pruned", t),
    ]:
        print(
            f"\t{n}: {v / basen:.2%} | {v / ntrees:.2%} | {v / t:.2%}",
        )
    return reduced_grammar, constraints
