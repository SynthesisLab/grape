from collections import defaultdict
from typing import TYPE_CHECKING, TypeVar, overload

from grape import types
from grape.automaton.tree_automaton import DFTA
from grape.program import Primitive, Program, Variable

# Solve circular import problem
if TYPE_CHECKING:
    from grape.dsl import DSL

T = TypeVar("T")


@overload
def specialize(
    grammar: DFTA[T, str], type_req: str, syntax: "DSL | None"
) -> DFTA[T, str]:
    pass


@overload
def specialize(
    grammar: DFTA[T, Program], type_req: str, syntax: "DSL | None"
) -> DFTA[T, Program]:
    pass


def specialize(
    grammar: DFTA[T, str] | DFTA[T, Program], type_req: str, syntax: "DSL | None"
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


def is_specialized(grammar: DFTA[T, str] | DFTA[T, Program]) -> bool:
    """
    Returns true if this grammar is specialized.
    """
    return "var0" in set(map(str, grammar.alphabet))


def type_request_from_specialized(
    grammar: DFTA[T, str] | DFTA[T, Program], dsl: "DSL"
) -> str:
    """
    Returns the type request of this specialized grammar.
    """
    # Guess variable type
    states_by_var = defaultdict(set)
    for (P, args), dst in grammar.rules.items():
        if str(P).startswith("var"):
            varno = int(str(P)[len("var") :])
            states_by_var[varno].add(dst)

    varno_to_type = {}

    for varno, states in states_by_var.items():
        possibles = None
        for (P, args), dst in grammar.rules.items():
            if str(P).startswith("var"):
                continue
            local = []
            for variant_type in types.all_variants(dsl.get_type(str(P))):
                for arg, arg_type in zip(args, types.arguments(variant_type)):
                    if arg in states:
                        local.append(arg_type)
            if local:
                if possibles is None:
                    possibles = set(local)
                else:
                    possibles.intersection_update(local)
        assert possibles is not None
        varno_to_type[varno] = "|".join(possibles)
    varlen = max(varno_to_type.keys())
    # Guess return type
    return_types = set()
    for dst in grammar.finals:
        for P, args in grammar.reversed_rules[dst]:
            if str(P).startswith("var"):
                rtype = varno_to_type[int(str(P)[len("var") :])]
            else:
                rtype = types.return_type(dsl.get_type(str(P)))
            return_types.add(rtype)
    dst_type = "none" if len(return_types) != 1 else list(return_types)[0]
    return "->".join([varno_to_type[i] for i in range(varlen + 1)]) + f"-> {dst_type}"


@overload
def despecialize(grammar: DFTA[T, str], type_req: str) -> DFTA[T, str]:
    pass


@overload
def despecialize(grammar: DFTA[T, Program], type_req: str) -> DFTA[T, Program]:
    pass


def despecialize(
    grammar: DFTA[T, str] | DFTA[T, Program], type_req: str
) -> DFTA[T, str] | DFTA[T, Program]:
    arg_types = types.arguments(type_req)
    vars2types = {i: arg_type for i, arg_type in enumerate(arg_types)}
    if isinstance(list(grammar.alphabet)[0], str):

        def update(letter: str):
            if letter.startswith("var"):
                return f"var_{vars2types[int(letter[len('var') :])]}"
            else:
                return letter
    else:

        def update(letter: Program):
            if isinstance(letter, Variable):
                return Primitive(f"var_{vars2types[letter.no]}")
            else:
                return letter

    out = grammar.map_alphabet(update)
    out.finals = out.all_states
    out.reduce()
    return out
