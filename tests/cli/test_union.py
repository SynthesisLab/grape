from grape.automaton_generator import (
    depth_constraint,
    grammar_by_saturation,
    size_constraint,
)
from grape.dsl import DSL


dsl = DSL(
    {
        "1": ("int", 1),
        "+": ("int -> int -> int", lambda x, y: x + y),
    }
)

max_size = 5


def test():
    size = grammar_by_saturation(dsl, "int->int", [size_constraint(0, 5)])
    depth = grammar_by_saturation(dsl, "int->int", [depth_constraint(0, 5)])
    inter = size.read_union(depth)
    other = grammar_by_saturation(
        dsl, "int->int", [depth_constraint(0, 5), size_constraint(0, 5)]
    )
    a = inter.trees_by_size(100)
    assert a == other.trees_by_size(100)
