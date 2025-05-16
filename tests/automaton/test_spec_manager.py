from grape.automaton.spec_manager import despecialize, specialize
from grape.automaton_generator import grammar_by_saturation
from grape.dsl import DSL


dsl = DSL(
    {
        "1": ("int", 1),
        "0": ("int", 0),
        "+": ("int -> int -> int", lambda x, y: x + y),
        "*": ("int -> int -> int", lambda x, y: x * y),
        "-": ("int -> int", lambda x: -x),
    }
)


def test():
    type_req = "int->int->int"
    grammar = grammar_by_saturation(dsl, type_req)
    prev = despecialize(grammar, type_req)
    spec = specialize(prev, type_req, dsl)
    assert spec.trees_until_size(100) == grammar.trees_until_size(100)
