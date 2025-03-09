from abc import ABC, abstractmethod
from typing import List


class Program(ABC):
    def __hash__(self):
        return self._hash

    def __repr__(self):
        return str(self)
    
    def same_var_used_more_than_once(self) -> tuple[bool, set[int]]:
        used = set()
        return self.__used_vars__(used), used

    @abstractmethod
    def __used_vars__(self, used: set[int]) -> bool:
        """
        Return true if the same var has been used twice.
        """
        pass


class Variable(Program):
    def __init__(self, no: int):
        self.no = no
        self._hash = no

    def __str__(self):
        return f"var{self.no}"
    
    def __used_vars__(self, used: set[int]) -> bool:
        if self.no in used:
            return True
        used.add(self.no)
        return False


class Primitive(Program):
    def __init__(self, name: str):
        self.name: str = name
        self._hash = hash(name)

    def __str__(self):
        return self.name
    
    def __used_vars__(self, used: set[int]) -> bool:
        return False


class Function(Program):
    def __init__(self, function: Program, arguments: List[Program]):
        self.function = function
        self.arguments = arguments
        self._hash = hash((function, *arguments))

    def __str__(self):
        args = ", ".join(map(str, self.arguments))
        return f"{self.function}({args})"
    
    def __used_vars__(self, used: set[int]) -> bool:
        if self.function.__used_vars__(used):
            return True
        return any(arg.__used_vars__(used) for arg in self.arguments)
