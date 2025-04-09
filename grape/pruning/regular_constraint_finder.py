from collections import defaultdict
import math
from grape.dsl import DSL
from grape.enumerator import Enumerator
from grape.evaluator import Evaluator
from grape.program import Program
from grape.automaton_generator import (
    grammar_by_saturation,
    grammar_from_memory,
    grammar_from_type_constraints_and_commutativity,
)
from grape.automaton.tree_automaton import DFTA
import grape.types as types

from tqdm import tqdm


def __infer_mega_type_req__(
    dsl: dict[str, tuple[str, callable]],
    rtype: str | None,
    max_size: int,
    samplable_types: set[str],
) -> str:
    # Capture max number of args of type that each type request needs
    max_per_type = defaultdict(int)
    for str_type, _ in dsl.values():
        args = types.arguments(str_type)
        count = defaultdict(int)
        nargs = len(args)
        for arg in args:
            count[arg] += 1
        for arg, n in count.items():
            per_copy = n
            cost_per_copy = nargs + 1
            # put your initial copy then all subsequent copies have cost
            n_copies = (
                1 + (max_size - cost_per_copy) / (cost_per_copy - 1)
                if max_size >= cost_per_copy
                else 0
            )
            j = int(math.ceil(n_copies * per_copy))
            max_per_type[arg] = max(max_per_type[arg], j)
    # Produce the number of args
    univ_type_req = []
    for t, n in max_per_type.items():
        if t in samplable_types:
            univ_type_req += [t] * n

    type_req = "->".join(univ_type_req + [str(rtype)])
    return type_req


def find_regular_constraints(
    dsl: DSL,
    evaluator: Evaluator,
    max_size: int,
    rtype: str | None,
    approx_constraints: list[tuple[Program, Program, str]],
    optimize: bool = False,
    no_loop: bool = False,
) -> tuple[DFTA[str, Program], list[tuple[Program, Program, str]]]:
    # Find all type requests
    type_req = __infer_mega_type_req__(
        dsl.primitives, rtype, max_size, set(evaluator.base_inputs.keys())
    )

    base_grammar = grammar_by_saturation(dsl, type_req)
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

    expected_trees = grammar.trees_by_size(max_size)
    original_expected_trees = base_grammar.trees_by_size(max_size)
    max_arity = dsl.max_arity()

    def estimate_total(size: int) -> tuple[int, float]:
        min_size = max(1, size - max_arity)
        ratio = sum(
            enumerator.count_programs_at_size(s) / expected_trees[s]
            for s in range(min_size, size + 1)
        ) / (size - min_size + 1)
        total = sum(enumerator.count_programs_at_size(i) for i in range(1, size + 1))
        total += int(
            sum(expected_trees[s] * ratio for s in range(size + 1, max_size + 1))
        )
        ratio = sum(
            enumerator.count_programs_at_size(s) / original_expected_trees[s]
            for s in range(min_size, size + 1)
        ) / (size - min_size + 1)

        return total, ratio

    # Generate all programs until some size
    pbar = tqdm(total=ntrees)
    pbar.set_description_str("obs. equiv.")
    gen = enumerator.enumerate_until_size(max_size + 1)
    program = next(gen)
    evaluator.eval(program, type_req)
    should_keep = True
    last_size = 1
    try:
        n = 0
        while True:
            program = gen.send(should_keep)
            representative = evaluator.eval(program, type_req)
            should_keep = representative is None
            n += 1
            if n & 15 == 0:
                pbar.update(16)
                if enumerator.current_size != last_size:
                    pbar.total, ratio = estimate_total(last_size)
                    pbar.set_postfix_str(f"est. ratio unique programs:{ratio:.0%}")
                    last_size += 1
                n = 0
    except StopIteration:
        pass
    pbar.update(n)
    pbar.close()
    evaluator.free_memory()
    reduced_grammar, t = grammar_from_memory(
        dsl, enumerator.memory, type_req, grammar.finals, optimize, no_loop
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
    allowed = []
    for dico in enumerator.memory.values():
        for progs in dico.values():
            allowed += [(p, type_req) for p in progs]
    return reduced_grammar, allowed
