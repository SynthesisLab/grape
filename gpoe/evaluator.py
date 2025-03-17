from itertools import product
from typing import Any, Optional, Tuple
from gpoe.program import Function, Primitive, Program, Variable
import gpoe.types as types


class Evaluator:
    def __init__(
        self,
        dsl: dict[str, tuple[str, callable]],
        inputs: dict[str, list],
        equal_dict: dict[str, callable],
    ):
        self.dsl = dsl
        self.equiv_classes: dict[str, dict[Any, Program]] = {}
        self.memoization: dict[Program, dict[Any, Any]] = {}
        self.base_inputs = inputs
        self.full_inputs_size = len(self.base_inputs[list(self.base_inputs.keys())[0]])
        self.full_inputs: dict[str, list] = {}

    def __gen_full_inputs__(self, type_req: str) -> None:
        if type_req not in self.full_inputs:
            args = types.arguments(type_req)
            possibles = [
                self.base_inputs[arg][i:-i] + self.base_inputs[arg][-i:]
                for i, arg in enumerate(args)
            ]
            elems = []
            for full_input in product(*possibles):
                elems.append(full_input)
                if len(elems) > self.full_inputs_size:
                    break
            self.full_inputs[type_req] = elems

    def eval(self, program: Program, type_req: str) -> Optional[Program]:
        if program in self.memoization:
            return None
        self.__gen_full_inputs__(type_req)
        # Compute its values
        outs = []
        for full_input in self.full_inputs[type_req]:
            out = self.__eval__(program, full_input)
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
