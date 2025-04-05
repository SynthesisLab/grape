from typing import Any, TypeVar
import sys
from grape import types
from grape.automaton.tree_automaton import DFTA
from grape.program import Primitive, Program


T = TypeVar("T")

TYPE_SEP = "|@>"


class DSL:
    def __init__(self, dsl: dict[str, tuple[str, callable]]):
        self.primitives: dict[str, tuple[str, callable]] = {}
        self.eval: dict[str, callable] = {}
        self.to_merge = {}

        for name, (stype, fn) in sorted(dsl.items()):
            self.eval[name] = fn
            variants = types.all_variants(stype)
            if len(variants) == 1:
                self.primitives[name] = (stype, fn)
            else:
                for sversion in variants:
                    new_name = f"{name}{TYPE_SEP}{sversion}"
                    self.primitives[new_name] = (sversion, fn)
                    self.to_merge[Primitive(new_name)] = Primitive(name)

    def apply(self, primitive: str, *args: Any) -> Any:
        return self.eval[primitive](*args)

    def semantic(self, primitive: str) -> Any:
        return self.eval[primitive]

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
        missing = set(self.eval.keys()).difference(set(map(str, grammar.alphabet)))
        if missing:
            print(
                f"[warning] the following primitives are not present in the grammar: {', '.join(missing)}",
                file=sys.stderr,
            )
        return not missing

    def merge_type_variants(self, grammar: DFTA[T, Program]) -> DFTA[T, Program]:
        return grammar.map_alphabet(lambda x: self.to_merge.get(x, x))
