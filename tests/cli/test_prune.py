import random

import pytest
from grape.automaton.loop_manager import LoopingAlgorithm, add_loops
from grape.automaton.spec_manager import respecialize, type_request_from_specialized
from grape.automaton_generator import grammar_by_saturation
from grape.dsl import DSL
from grape.enumerator import Enumerator
from grape.evaluator import Evaluator
from grape.pruning.equivalence_class_manager import EquivalenceClassManager
from grape.pruning.obs_equiv_pruner import prune


def sample_inputs(nsamples: int, sample_dict: dict[str, callable]) -> dict[str, list]:
    inputs = {}
    for sampled_type, sample_fn in sample_dict.items():

        def eq_fn(x, y):
            return x == y

        sampled_inputs = []
        tries = 0
        while len(sampled_inputs) < nsamples and tries < 100:
            sampled = sample_fn()
            if all(not eq_fn(sampled, el) for el in sampled_inputs):
                sampled_inputs.append(sampled)
                tries = 0
            tries += 1
        while len(sampled_inputs) < nsamples:
            sampled_inputs += sampled_inputs
            sampled_inputs = sampled_inputs[:nsamples]

        inputs[sampled_type] = sampled_inputs
    return inputs


random.seed(1)
INT_SIZE = 32
MAXI = (1 << INT_SIZE) - 1
assert len(f"{MAXI:b}") == INT_SIZE, len(f"{MAXI:b}")
# Given a type provides a function to sample one element


def signed_masking(n: int, mask: int = MAXI) -> int:
    return n & mask if n > 0 else -(-n & mask)


sample_dict = {
    "int": lambda: signed_masking(random.randint(-MAXI, MAXI), MAXI),
    "bool": lambda: random.uniform(0, 1) > 0.5,
}

inputs = sample_inputs(50, sample_dict)


dsl = DSL(
    {
        "1": ("int", 1),
        "0": ("int", 0),
        "+": ("int -> int -> int", lambda x, y: x + y),
        "*": ("int -> int -> int", lambda x, y: x * y),
        "-": ("int -> int", lambda x: -x),
        "True": ("bool", True),
        ">0": ("int -> bool", lambda x: x > 0),
        "ite": (
            "bool -> 'a [bool|int] -> 'a -> 'a",
            lambda b, pos, neg: pos if b else neg,
        ),
    }
)
evaluator = Evaluator(dsl, inputs, {}, set())
max_size = 5
algorithms = [LoopingAlgorithm.OBSERVATIONAL_EQUIVALENCE, LoopingAlgorithm.GRAPE]


def comp_by_enum(grammars: list, tr: str, max_size: int):
    """
    args = [g1, g2]
    check g1 == g2 (exactly in this order)
    """
    enums: list[tuple[Enumerator, Evaluator]] = []
    for g in grammars:
        evaluator = Evaluator(dsl, inputs, {}, set())
        e = Enumerator(g)
        gen = e.enumerate_until_size(max_size + 1)
        p = next(gen)
        evaluator.eval(p, tr)
        should_keep = True
        try:
            while True:
                p = gen.send(should_keep)
                should_keep = evaluator.eval(p, tr) is None
        except StopIteration:
            pass
        enums.append((e, evaluator))

    std, evalstd = enums.pop()
    for other, evalother in enums:
        for size in range(max_size + 1):
            a = other.count_programs_at_size(size)
            b = std.count_programs_at_size(size)
            if a != b:
                programs = []
                for state in other.states:
                    programs += other.memory[state][size]
                p2 = []
                for state in std.states:
                    p2 += std.memory[state][size]
                diff = set(p2).symmetric_difference(programs)
                true_diffL = set()
                true_diffR = set()
                for p in diff:
                    pp = evalstd.eval(p, tr) or evalother.eval(p, tr)
                    if pp is None or pp not in diff:
                        true_diff = true_diffL if p in programs else true_diffR
                        true_diff.add(p)
                assert true_diffL == true_diffR, (
                    f"size={size} count(g1)-count(g2)={b - a}"
                )


def test_prune():
    manager = EquivalenceClassManager()
    out = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    tr = "int->int"
    g = grammar_by_saturation(dsl, tr)
    spec_out = respecialize(out, tr, type_request_from_specialized(out, dsl), dsl)
    comp_by_enum([spec_out, g], tr, max_size)


def test_incremental_same_size():
    manager = EquivalenceClassManager()
    out = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    incremental = prune(
        dsl, evaluator, manager, max_size=max_size, rtype="int", base_grammar=out
    )
    assert out.rules == incremental.rules
    assert out.finals == incremental.finals


@pytest.mark.parametrize("algo", algorithms)
def test_incremental_same_size_with_loops(algo: LoopingAlgorithm):
    manager = EquivalenceClassManager()
    out = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    out = add_loops(out, dsl, algo)

    incremental = prune(
        dsl, evaluator, manager, max_size=max_size, rtype="int", base_grammar=out
    )
    incremental = add_loops(incremental, dsl, algo)

    assert out.rules == incremental.rules
    assert out.finals == incremental.finals


@pytest.mark.parametrize("algo", algorithms)
def test_incremental_next_size(algo: LoopingAlgorithm):
    manager = EquivalenceClassManager()
    evaluator = Evaluator(dsl, inputs, {}, set())
    out = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    out = add_loops(out, dsl, algo)
    evaluator.free_memory()
    incremental = prune(
        dsl, evaluator, manager, max_size=max_size + 1, rtype="int", base_grammar=out
    )
    evaluator.free_memory()
    direct = prune(dsl, evaluator, manager, max_size=max_size + 1, rtype="int")
    comp_by_enum(
        [incremental, direct], type_request_from_specialized(direct, dsl), max_size + 1
    )


def test_is_superset():
    evaluator = Evaluator(dsl, inputs, {}, set())

    manager = EquivalenceClassManager()
    out = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    tr = "int->int"
    base = grammar_by_saturation(dsl, tr)
    evaluator = Evaluator(dsl, inputs, {}, set())
    ebase = Enumerator(base)
    gen = ebase.enumerate_until_size(max_size)
    p = next(gen)
    should_keep = evaluator.eval(p, tr) is None
    try:
        while True:
            p = gen.send(should_keep)
            should_keep = evaluator.eval(p, tr) is None
    except StopIteration:
        pass
    e = Enumerator(respecialize(out, tr, type_request_from_specialized(out, dsl), dsl))
    gen = e.enumerate_until_size(max_size)
    p = next(gen)
    try:
        while True:
            gen.send(True)
    except StopIteration:
        pass

    new_memory_to_size = {}
    old_memory_to_size = {}
    for value in e.memory.values():
        for size, programs in value.items():
            if size not in new_memory_to_size:
                new_memory_to_size[size] = []
            new_memory_to_size[size] += programs
    for value in ebase.memory.values():
        for size, programs in value.items():
            if size not in old_memory_to_size:
                old_memory_to_size[size] = []
            old_memory_to_size[size] += programs

    sizes = set(new_memory_to_size.keys()) | set(old_memory_to_size.keys())
    for size in sizes:
        assert size in new_memory_to_size
        assert set(old_memory_to_size.get(size, [])).issubset(
            set(new_memory_to_size[size])
        )
