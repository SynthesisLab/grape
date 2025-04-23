from grape.dsl import DSL


def test_mba():
    dsl_dict: dict[str, tuple[str, callable]] = {
        "+": ("int -> int -> int", lambda x, y: x + y),
        "*": ("int -> int -> int", lambda x, y: x * y),
        "-": ("int -> int -> int", lambda x, y: x - y),
        "^": ("int -> int -> int", lambda x, y: x ^ y),
        "&": ("int -> int -> int", lambda x, y: x & y),
        "|": ("int -> int -> int", lambda x, y: x | y),
        "~": ("int -> int", lambda x: ~x),
        "1": ("int", 1),
    }

    _dsl = DSL(dsl_dict)


def test_type_hints():
    def add(x: int, y: int) -> int:
        return x + y

    def mul(x: int, y: int) -> int:
        return x * y

    def sub(x: int, y: int) -> int:
        return x - y

    dsl_dict: dict[str, tuple[str, callable]] = {
        "+": add,
        "*": mul,
        "-": sub,
        "1": 1,
    }

    _dsl = DSL(dsl_dict)
