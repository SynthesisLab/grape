from collections import defaultdict
import math
from typing import Callable
from grape.automaton.spec_manager import specialize
from grape.dsl import DSL
from grape.enumerator import Enumerator
from grape.evaluator import Evaluator
from grape.program import Primitive, Program, Variable
from grape.automaton_generator import (
    grammar_by_saturation,
    grammar_from_memory,
    commutativity_constraint,
)
from grape.automaton.tree_automaton import DFTA
import grape.pruning.commutativity_pruner as commutativity_pruner
from grape.pruning.equivalence_class_manager import EquivalenceClassManager
import grape.types as types

from tqdm import tqdm


def __infer_mega_type_req__(
    dsl: dict[str, tuple[str, Callable]],
    rtype: str | None,
    max_size: int,
    samplable_types: set[str],
) -> str:
    # Capture max number of args of type that each type request needs
    max_per_type = defaultdict(int)
    for str_type, _ in dsl.values():
        args = types.arguments(str_type)
        count: dict[str, int] = defaultdict(int)
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


def __get_base_grammar__(
    dsl: DSL,
    evaluator: Evaluator,
    manager: EquivalenceClassManager,
    max_size: int,
    base_dfta: DFTA | None,
    type_req: str,
):
    base_grammar = grammar_by_saturation(dsl, type_req)
    if base_dfta is None:
        commutatives = commutativity_pruner.prune(dsl, evaluator, manager)
        grammar = grammar_by_saturation(
            dsl,
            type_req,
            [commutativity_constraint(dsl, commutatives, type_req)],
        )
    else:
        base_grammar = dsl.map_to_variants(base_dfta)
        base_grammar = specialize(base_grammar, type_req, dsl)
        base_grammar = base_grammar.map_alphabet(
            lambda x: Variable(int(x[len("var") :]))
            if str(x).startswith("var")
            else Primitive(x)
        )
        grammar = base_grammar
    base_trees_by_size = base_grammar.trees_by_size(max_size)
    enum_ntrees = grammar.trees_until_size(max_size)
    return grammar, base_trees_by_size, enum_ntrees


def prune(
    dsl: DSL,
    evaluator: Evaluator,
    manager: EquivalenceClassManager,
    max_size: int,
    rtype: str | None = None,
    base_grammar: DFTA | None = None,
) -> tuple[DFTA[str, Program], str]:
    # Find all type requests
    type_req = __infer_mega_type_req__(
        dsl.primitives, rtype, max_size, set(evaluator.base_inputs.keys())
    )
    grammar, base_expected_trees, enum_ntrees = __get_base_grammar__(
        dsl,
        evaluator,
        manager,
        max_size,
        base_grammar,
        type_req,
    )
    base_ntrees = sum(base_expected_trees.values())

    enumerator = Enumerator(grammar)

    expected_trees = grammar.trees_by_size(max_size)
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
            enumerator.count_programs_at_size(s) / base_expected_trees[s]
            for s in range(min_size, size + 1)
        ) / (size - min_size + 1)

        return total, ratio

    # Generate all programs until some size
    pbar = tqdm(total=enum_ntrees)
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
            if not should_keep:
                manager.add_merge(program, representative)
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
        enumerator.memory, type_req, grammar.finals
    )
    print("at size:", max_size)
    print(
        "\tmethod: ratio no pruning | ratio enum. | ratio pruned",
    )
    for s, v in [
        ("no pruning", base_ntrees),
        ("commutativity pruned", enum_ntrees),
        ("pruned", t),
    ]:
        print(
            f"\t{s}: {v / base_ntrees:.2%} | {v / enum_ntrees:.2%} | {v / t:.2%}",
        )
    return reduced_grammar, type_req
