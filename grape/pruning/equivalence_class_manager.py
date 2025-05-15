import json
from grape.program import Program


class EquivalenceClassManager:
    def __init__(self):
        self.classes: dict[Program, set[Program]] = {}

    def new_class(self, representative: Program):
        """
        Create a new class of equivalence.
        Assumes class does not already exist.
        """
        assert representative not in self.classes
        self.classes[representative] = set()

    def add_to_class(self, program: Program, representative: Program):
        """
        Add a program to an already existing equivalence class.
        Assumes class already exists.
        """
        self.classes[representative].add(program)

    def add_merge(self, program: Program, representative: Program):
        """
        Add a program to an already existing equivalence class.
        Assumes nothing so it creates a new class if it does not exist.
        """
        if representative not in self.classes:
            self.new_class(representative)
        self.add_to_class(program, representative)

    def to_json(self) -> str:
        str_classes = sorted(
            [
                {"representative": str(key), "elements": list(map(str, value))}
                for key, value in self.classes.items()
            ],
            key=lambda x: (x["representative"], len(x["elements"])),
            reverse=True,
        )
        return json.dumps(str_classes)
