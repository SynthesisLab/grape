from itertools import product
from collections import defaultdict
from typing import Any, Dict, Generator, List, Tuple
from gpoe.program import Program, Function
from gpoe.tree_automaton import DFTA
from gpoe.partitions import integer_partitions


class Enumerator:
    def __init__(self, grammar: DFTA[Any, Program]):
        self.grammar = grammar
        self.states = sorted(self.grammar.states)
        self.__setup__()

    def __setup__(self) -> None:
        # Memorize State -> Size -> Programs
        self.memory: Dict[Any, Dict[int, List[Program]]] = {}
        for state in self.states:
            self.memory[state] = defaultdict(list)
        # Memorize (State, State, ...) -> Size -> (Program, Program, ...)
        self.memory_combinations: Dict[
            Tuple[Any, ...], Dict[int, List[Tuple[Program, ...]]]
        ] = {}
        for state in self.states:
            for derivation in self.grammar.reversed_rules[state]:
                _, args = derivation
                if len(args) > 0 and args not in self.memory_combinations:
                    self.memory_combinations[args] = {}
        self.current_size = 0

    def __query_combinations__(
        self, args: Tuple[Any, ...], size: int
    ) -> Generator[Tuple[Program, ...], None, None]:
        # Use cache if available
        if size in self.memory_combinations[args]:
            for el in self.memory_combinations[args][size]:
                yield el
        # Iterate over all combinations
        else:
            mem = []
            for size_requests in integer_partitions(len(args), size):
                possibles = [
                    self.memory[state][sub_size]
                    for state, sub_size in zip(args, size_requests)
                ]
                if any(len(x) == 0 for x in possibles):
                    continue
                for combination in product(*possibles):
                    yield combination
                    mem.append(combination)
            self.memory_combinations[args][size] = mem

    def enumerate_until_size(self, size: int) -> Generator[Program, bool, None]:
        """
        Enumerate all programs until programs reach target size (excluded).
        """

        while self.current_size < size:
            self.current_size += 1
            # Special case: size==1
            if self.current_size == 1:
                for state in self.states:
                    for derivation in self.grammar.reversed_rules[state]:
                        letter, args = derivation
                        if len(args) == 0:
                            should_keep = True
                            if state in self.grammar.finals:
                                should_keep = yield letter
                            if should_keep:
                                self.memory[state][1].append(letter)
            else:
                for state in self.states:
                    for derivation in self.grammar.reversed_rules[state]:
                        letter, args = derivation
                        if len(args) > 0:
                            for combination in self.__query_combinations__(
                                args, self.current_size - 1
                            ):
                                program = Function(letter, list(combination))
                                if state in self.grammar.finals:
                                    should_keep = yield program
                                    if should_keep:
                                        self.memory[state][self.current_size].append(
                                            program
                                        )
                                else:
                                    self.memory[state][self.current_size].append(
                                        program
                                    )
