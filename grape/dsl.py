from typing import Any, Callable, TypeVar, overload
import sys
from grape import types
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
            if len(variants) == 1:
                self.primitives[name] = (stype, fn)
                self.eval[name] = fn
            else:
                for sversion in variants:
                    new_name = self.__name_variant__(name, sversion)
                    self.primitives[new_name] = (sversion, fn)
                    self.eval[new_name] = fn
                    self.to_merge[Primitive(new_name)] = Primitive(name)

    def __name_variant__(self, primitive: str, str_type: str) -> str:
        return f"{primitive}{TYPE_SEP}{str_type}"

    def max_arity(self) -> int:
        return max(len(types.arguments(t)) for t, _ in self.primitives.values())

    def apply(self, primitive: str, *args: Any) -> Any:
        return self.eval[primitive](*args)

    def semantic(self, primitive: str) -> Any:
        return self.eval[primitive]

    def get_state_types(
        self, automaton: DFTA[T, str | Program], type_req: str | None = None
    ) -> dict[T, str]:
        """
        type_req is necessary if automaton is specialized
        """
        # Assumes types variants are not present.
        specialized = "var0" in set(map(str, automaton.alphabet))
        if specialized:
            assert type_req is not None, (
                "type request must be specified for a specialized automaton!"
            )
            arg_types = types.arguments(type_req)

        state_to_type: dict[Any, str] = {}
        elements = list(automaton.rules.items())
        while elements:
            (P, args), dst = elements.pop()
            if not specialized and str(P).startswith("var_"):
                Ptype = str(P)[len("var_") :]
            elif specialized and str(P).startswith("var"):
                Ptype = arg_types[int(str(P)[len("var") :])]
            elif specialized:
                Ptype = self.primitives[str(P)][0]
            else:
                base_Ptype = self.original_primitives[str(P)]
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
                assert state_to_type[dst] == types.return_type(Ptype)
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

    def check_all_variants_present(self, grammar: DFTA[Any, Program]) -> bool:
        missing = set(self.primitives.keys()).difference(
            set(map(str, grammar.alphabet))
        )

        if any(TYPE_SEP in t for t in missing):
            missing_version = {t for t in missing if TYPE_SEP in t}
            print(
                f"[warning] the following primitives are not present in some versions in the grammar: {', '.join(missing_version)}",
                file=sys.stderr,
            )
        return not missing

    def check_all_primitives_present(self, grammar: DFTA[Any, Program]) -> bool:
        missing = set(self.original_primitives.keys()).difference(
            set(map(str, grammar.alphabet))
        )
        if missing:
            print(
                f"[warning] the following primitives are not present in the grammar: {', '.join(missing)}",
                file=sys.stderr,
            )
        return not missing

    def merge_type_variants(self, grammar: DFTA[T, Program]) -> DFTA[T, Program]:
        return grammar.map_alphabet(lambda x: self.to_merge.get(x, x))
