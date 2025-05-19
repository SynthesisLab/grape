from collections import defaultdict
import random
from typing import Any, Callable, Generator, Optional
from grape.dsl import DSL
from grape.program import Function, Primitive, Program, Variable
import grape.types as types


def random_product(
    prng: random.Random, *elements: list
) -> Generator[tuple, None, None]:
    while True:
        yield tuple(prng.choice(li) for li in elements)


class Evaluator:
    def __init__(
        self,
        dsl: DSL,
        inputs: dict[str, list],
        equal_dict: dict[str, Callable],
        skip_exceptions: set,
        seed: int = 1,
    ):
        self.dsl = dsl
        self.equiv_classes: dict[str, dict[Any, Program]] = defaultdict(dict)
        self.memoization: dict[Program, dict[Any, Any]] = defaultdict(dict)
        self.rtypes: dict[str, str] = {
            p: types.return_type(stype) for p, (stype, _) in dsl.primitives.items()
        }
        self.base_inputs = inputs
        self.full_inputs_size = len(self.base_inputs[list(self.base_inputs.keys())[0]])
        self.full_inputs: dict[str, list] = {}
        self.skip_exceptions = skip_exceptions
        self.prng = random.Random(seed)

    def clean_memoisation(self) -> None:
        self.memoization.clear()

    def free_memory(self) -> None:
        self.equiv_classes.clear()
        self.memoization.clear()
        self.full_inputs.clear()

    def __gen_full_inputs__(self, type_req: str) -> None:
        if type_req not in self.full_inputs:
            args = types.arguments(type_req)
            possibles = [list(set(self.base_inputs[arg])) for arg in args]
            for el in possibles:
                self.prng.shuffle(el)
            elems = set()
            tries = 0
            max_tries = 100 * len(possibles)
            for full_input in random_product(self.prng, *possibles):
                tries = tries + 1 if full_input in elems else 0
                elems.add(full_input)
                if len(elems) > self.full_inputs_size or tries > max_tries:
                    break
            self.full_inputs[type_req] = list(elems)

    def __return_type__(self, program: Program, type_req: str) -> str:
        match program:
            case Variable(no):
                return types.arguments(type_req)[no]
            case Primitive(name):
                return self.rtypes[name]
            case Function(func):
                return self.rtypes[func.name]
            case _:
                raise ValueError

    def eval(self, program: Program, type_req: str) -> Optional[Program]:
        if program in self.memoization:
            return None
        self.__gen_full_inputs__(type_req)
        # Compute its values
        outs = []
        for full_input in self.full_inputs[type_req]:
            try:
                out = self.__eval__(program, full_input)
            except Exception as e:
                if any(isinstance(e, cls) for cls in self.skip_exceptions):
                    out = None
                else:
                    raise e
            outs.append(out)
        # Check equivalence class
        rtype = self.__return_type__(program, type_req)
        key = tuple(outs)
        representative = self.equiv_classes[rtype].get(key, None)
        if representative is None:
            self.equiv_classes[rtype][key] = program
        else:
            del self.memoization[program]
        return representative

    def __eval__(self, program: Program, full_input: tuple[Any, ...]) -> Any:
        mem = self.memoization[program]
        if full_input in mem:
            return mem[full_input]
        # Compute value
        out = None
        match program:
            case Variable(no):
                out = full_input[no]
            case Primitive(name):
                out = self.dsl.semantic(name)
            case Function(func):
                fun = self.dsl.semantic(func.name)
                arg_vals = [self.__eval__(arg, full_input) for arg in program.arguments]
                out = fun(*arg_vals)

        mem[full_input] = out
        return out
