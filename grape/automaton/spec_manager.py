from typing import TypeVar, overload

from grape import types
from grape.automaton.tree_automaton import DFTA
from grape.dsl import DSL
from grape.program import Program, Variable


T = TypeVar("T")


@overload
def specialize(
    grammar: DFTA[T, str], type_req: str, syntax: DSL | None
) -> DFTA[T, str]:
    pass


@overload
def specialize(
    grammar: DFTA[T, Program], type_req: str, syntax: DSL | None
) -> DFTA[T, Program]:
    pass


def specialize(
    grammar: DFTA[T, str] | DFTA[T, Program], type_req: str, syntax: DSL | None
) -> DFTA[T, str] | DFTA[T, Program]:
    if isinstance(list(grammar.alphabet)[0], str):

        def make_var(i: int):
            return f"var{i}"
    else:

        def make_var(i: int):
            return Variable(i)

    arg_types = types.arguments(type_req)
    rtype = types.return_type(type_req)
    whatever = rtype.lower() == "none"
    new_rules = {}
    for (P, args), dst in grammar.rules.items():
        if str(P).startswith("var_"):
            var_type = str(P)[len("var_") :]
            for i, arg_type in enumerate(arg_types):
                if arg_type == var_type:
                    new_rules[(make_var(i), args)] = dst
        else:
            new_rules[(P, args)] = dst

    if whatever or syntax is None:
        return DFTA(new_rules, set(list(grammar.finals)))
    else:
        state_to_type = syntax.get_state_types(grammar)
        return DFTA(
            new_rules, set(s for s in grammar.finals if state_to_type[s] == rtype)
        )
