import random
from grape.automaton_generator import grammar_by_saturation
from grape.dsl import DSL
from grape.enumerator import Enumerator
from grape.evaluator import Evaluator
from grape.program import str_to_program


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
    }
)
tr = "int->int"
grammar = grammar_by_saturation(dsl, tr)
max_size = 5


def test_evaluator_seeding():
    e1 = Evaluator(dsl, inputs, {}, set(), seed=5)
    e2 = Evaluator(dsl, inputs, {}, set(), seed=5)

    e = Enumerator(grammar)
    g = e.enumerate_until_size(max_size)
    p = next(g)
    assert e1.eval(p, tr) == e2.eval(p, tr)

    try:
        while True:
            p = g.send(True)
            assert e1.eval(p, tr) == e2.eval(p, tr)
    except StopIteration:
        pass


def test_evaluator_seeding_default_behaviour():
    e1 = Evaluator(dsl, inputs, {}, set())
    e2 = Evaluator(dsl, inputs, {}, set())

    e = Enumerator(grammar)
    g = e.enumerate_until_size(max_size)
    p = next(g)
    assert e1.eval(p, tr) == e2.eval(p, tr)

    try:
        while True:
            p = g.send(True)
            assert e1.eval(p, tr) == e2.eval(p, tr)
    except StopIteration:
        pass


def test_evaluator_representatives():
    e = Evaluator(dsl, inputs, {}, set())
    r = str_to_program("1")
    assert e.eval(r, tr) is None
    p = str_to_program("1")
    assert e.eval(p, tr) is None
    p = str_to_program("(+ 0 1)")
    assert e.eval(p, tr) == r
    p = str_to_program("1")
    assert e.eval(p, tr) is None
    p = str_to_program("(+ (+ 0 0) (+ 1 0))")
    assert e.eval(p, tr) == r


def test_skip_exception():
    dsl = DSL(
        {
            "1": ("int", 1),
            "0": ("int", 0),
            "+": ("int -> int -> int", lambda x, y: x + y),
            "/": ("int -> int -> int", lambda x, y: x // y),
        }
    )
    tr = "int->int"

    e = Evaluator(dsl, inputs, {}, set())
    r = str_to_program("(/ 1 0)")
    try:
        e.eval(r, tr)
        assert False
    except ZeroDivisionError:
        pass
    e = Evaluator(dsl, inputs, {}, {ZeroDivisionError})
    try:
        e.eval(r, tr)
    except ZeroDivisionError:
        assert False
