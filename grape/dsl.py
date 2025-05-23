from typing import Any, Callable, TypeVar, overload
from grape import types
from grape.automaton import spec_manager
from grape.automaton.tree_automaton import DFTA
from grape.program import Primitive, Program


T = TypeVar("T")

TYPE_SEP = "|@>"


class DSL:
    def __init__(self, dsl: dict[str, tuple[str, Callable] | Callable]):
        self.primitives: dict[str, tuple[str, Callable]] = {}
        self.original_primitives: dict[str, str] = {}
        self.eval: dict[str, Callable] = {}
        self.to_merge: dict[Program, Program] = {}

        for name, item in sorted(dsl.items()):
            if isinstance(item, tuple):
                (stype, fn) = item
            else:
                (stype, fn) = types.annotations_to_type_str(item), item
            self.original_primitives[name] = stype
            variants = types.all_variants(stype)
            self.eval[name] = fn
            if len(variants) == 1:
                self.primitives[name] = (stype, fn)
            else:
                for sversion in variants:
                    new_name = self.__name_variant__(name, sversion)
                    self.primitives[new_name] = (sversion, fn)
                    self.to_merge[Primitive(new_name)] = Primitive(name)

    def __name_variant__(self, primitive: str, str_type: str) -> str:
        return f"{primitive}{TYPE_SEP}{str_type}"

    def get_type(self, primitive: str) -> str:
        """
        Get the type of the specified primitive.
        Works both with and without variants.
        """
        if TYPE_SEP in primitive:
            return self.primitives[primitive][0]
        else:
            return self.original_primitives[primitive]

    def max_arity(self) -> int:
        return max(len(types.arguments(t)) for t, _ in self.primitives.values())

    def semantic(self, primitive: str) -> Any:
        """
        Get the semantic of the specified primitive.
        Works both with and without variants.
        """
        if TYPE_SEP in primitive:
            return self.primitives[primitive][1]
        else:
            return self.eval[primitive]

    def get_state_types(self, automaton: DFTA[T, str | Program]) -> dict[T, str]:
        """
        Get a mapping from states to types.
        """
        # Assumes types variants are not present.
        specialized = spec_manager.is_specialized(automaton)
        if specialized:
            guessed_tr = spec_manager.type_request_from_specialized(automaton, self)
            arg_types = types.arguments(guessed_tr)
        state_to_type: dict[Any, str] = {}
        elements = list(automaton.rules.items())
        while elements:
            (P, args), dst = elements.pop()
            if not specialized and str(P).startswith("var_"):
                Ptype = str(P)[len("var_") :]
            elif specialized and str(P).startswith("var"):
                Ptype = arg_types[int(str(P)[len("var") :])]
            else:
                base_Ptype = self.get_type(str(P))
                all_possibles = types.all_variants(base_Ptype)
                for i, arg_state in enumerate(args):
                    if arg_state not in state_to_type:
                        continue
                    all_possibles = [
                        t
                        for t in all_possibles
                        if state_to_type[arg_state] == types.arguments(t)[i]
                    ]
                if len(all_possibles) > 1:
                    elements.insert(0, ((P, args), dst))
                    continue
                else:
                    assert len(all_possibles) > 0, (
                        f"failed to find coherent primitive '{P}' in DSL during analysis of:\n\t{P} {args} -> {dst}\n\t{P} {tuple(map(lambda x: state_to_type.get(x, '?'), args))} -> {state_to_type.get(dst, '?')}"
                    )
                    Ptype = all_possibles.pop()
            if dst in state_to_type:
                all_types = set()
                for variant in types.all_variants(Ptype):
                    all_types.add(types.return_type(variant))
                assert state_to_type[dst] in all_types
            else:
                state_to_type[dst] = types.return_type(Ptype)
        return state_to_type

    @overload
    def map_to_variants(self, automaton: DFTA[T, Program]) -> DFTA[T, Program]:
        pass

    @overload
    def map_to_variants(self, automaton: DFTA[T, str]) -> DFTA[T, str]:
        pass

    def map_to_variants(
        self, automaton: DFTA[T, Program] | DFTA[T, str]
    ) -> DFTA[T, Program] | DFTA[T, str]:
        """
        Produce the DFTA with the right type variants.
        In other words it replaces generic primitives with their variants based on the types of the transitions.

        """
        state2type = self.get_state_types(automaton)
        if isinstance(list(automaton.alphabet)[0], str):

            def make(letter: str):
                return letter
        else:

            def make(letter: str):
                return Primitive(letter)

        new_rules = {}

        for (P, args), dst in automaton.rules.items():
            str_type = self.original_primitives.get(str(P))
            variants = [] if str_type is None else types.all_variants(str_type)
            if len(variants) <= 1:
                new_rules[(P, args)] = dst
            else:
                variants = [
                    t for t in variants if types.return_type(t) == state2type[dst]
                ]
                for i, arg_state in enumerate(args):
                    variants = [
                        t
                        for t in variants
                        if types.arguments(t)[i] == state2type[arg_state]
                    ]
                assert len(variants) == 1
                newP = make(self.__name_variant__(str(P), variants.pop()))
                new_rules[(newP, args)] = dst
        return DFTA(new_rules, set(list(automaton.finals)))

    def find_missing_variants(self, grammar: DFTA[Any, Program]) -> set[str]:
        missing = set(self.primitives.keys()).difference(
            set(map(str, grammar.alphabet))
        )

        if any(TYPE_SEP in t for t in missing):
            missing_version = {t for t in missing if TYPE_SEP in t}
            missing = missing_version
        return missing

    def find_missing_primitives(self, grammar: DFTA[Any, Program]) -> set[str]:
        return set(self.original_primitives.keys()).difference(
            set(map(str, grammar.alphabet))
        )

    def merge_type_variants(self, grammar: DFTA[T, Program]) -> DFTA[T, Program]:
        return grammar.map_alphabet(lambda x: self.to_merge.get(x, x))
