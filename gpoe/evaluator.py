from itertools import product
import random
from typing import Any, Optional, Tuple
from gpoe.program import Function, Primitive, Program, Variable
import gpoe.types as types


class Evaluator:
    def __init__(
        self,
        dsl: dict[str, tuple[str, callable]],
        inputs: dict[str, list],
        equal_dict: dict[str, callable],
        skip_exceptions: set,
        seed: int = 1,
    ):
        self.dsl = dsl
        self.equiv_classes: dict[str, dict[Any, Program]] = {}
        self.memoization: dict[Program, dict[Any, Any]] = {}
        self.base_inputs = inputs
        self.full_inputs_size = len(self.base_inputs[list(self.base_inputs.keys())[0]])
        self.full_inputs: dict[str, list] = {}
        self.skip_exceptions = skip_exceptions
        self.prng = random.Random(seed)

    def clean_memoisation(self) -> None:
        self.memoization = {}

    def free(self) -> None:
        del self.dsl
        del self.equiv_classes
        del self.memoization
        del self.full_inputs

    def __gen_full_inputs__(self, type_req: str) -> None:
        if type_req not in self.full_inputs:
            args = types.arguments(type_req)
            possibles = [list(set(self.base_inputs[arg])) for arg in args]
            for el in possibles:
                self.prng.shuffle(el)
            elems = set()
            for full_input in product(*possibles):
                elems.add(full_input)
                if len(elems) > self.full_inputs_size:
                    break
            self.full_inputs[type_req] = list(elems)

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
        rtype = types.return_type(type_req)
        key = tuple(outs)
        if rtype not in self.equiv_classes:
            self.equiv_classes[rtype] = {}
        representative = self.equiv_classes[rtype].get(key, None)
        if representative is None:
            self.equiv_classes[rtype][key] = program
        else:
            del self.memoization[program]
        return representative

    def __eval__(self, program: Program, full_input: Tuple[Any, ...]) -> Any:
        if program in self.memoization:
            if full_input in self.memoization[program]:
                return self.memoization[program][full_input]
        else:
            self.memoization[program] = {}
        # Compute value
        out = None
        if isinstance(program, Variable):
            out = full_input[program.no]
        elif isinstance(program, Primitive):
            out = self.dsl[program.name][1]
        elif isinstance(program, Function):
            fun = self.__eval__(program.function, full_input)
            arg_vals = [self.__eval__(arg, full_input) for arg in program.arguments]
            out = fun(*arg_vals)
        self.memoization[program][full_input] = out
        return out
