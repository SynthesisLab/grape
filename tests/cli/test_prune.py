import random
from grape.automaton.loop_manager import add_loops
from grape.automaton.spec_manager import specialize
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


sample_dict = {"int": lambda: signed_masking(random.randint(-MAXI, MAXI), MAXI)}

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
max_size = 4


def comp_by_enum(grammars: list, tr: str, max_size: int):
    enums: list[Enumerator] = []
    for g in grammars:
        e = Enumerator(g)
        gen = e.enumerate_until_size(max_size)
        p = next(gen)
        evaluator.eval(p, tr)
        should_keep = True
        try:
            while True:
                p = gen.send(should_keep)
                should_keep = evaluator.eval(p, tr) is None
        except StopIteration:
            pass
        enums.append(e)
    std = enums.pop()
    for other in enums:
        for size in range(max_size):
            assert other.count_programs_at_size(size) == std.count_programs_at_size(
                size
            )


def test_prune():
    manager = EquivalenceClassManager()
    out, tr = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    tr = "int->int"
    g = grammar_by_saturation(dsl, tr)
    spec_out = specialize(out, tr, dsl)
    comp_by_enum([spec_out, g], tr, max_size + 1)


def test_incremental_same_size():
    manager = EquivalenceClassManager()
    out, tr = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    incremental, tr = prune(
        dsl, evaluator, manager, max_size=max_size, rtype="int", base_grammar=out
    )
    assert out.rules == incremental.rules
    assert out.finals == incremental.finals


def test_incremental_same_size_with_loops():
    manager = EquivalenceClassManager()
    out, tr = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    out = add_loops(
        out,
        dsl,
    )

    incremental, tr = prune(
        dsl, evaluator, manager, max_size=max_size, rtype="int", base_grammar=out
    )
    incremental = add_loops(
        incremental,
        dsl,
    )

    assert out.rules == incremental.rules
    assert out.finals == incremental.finals


def test_incremental_next_size():
    manager = EquivalenceClassManager()
    out, tr = prune(dsl, evaluator, manager, max_size=max_size, rtype="int")
    out = add_loops(
        out,
        dsl,
    )
    incremental, tr = prune(
        dsl, evaluator, manager, max_size=max_size + 1, rtype="int", base_grammar=out
    )
    direct, tr = prune(dsl, evaluator, manager, max_size=max_size + 1, rtype="int")
    assert direct.rules == incremental.rules
    assert direct.finals == incremental.finals
