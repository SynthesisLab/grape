from grape.types import (
    annotations_to_type_str,
    return_type,
    arguments,
    parse,
    all_variants,
)


def test_constants_annotation():
    ONE = 1
    EMPTY = ""
    assert annotations_to_type_str(ONE) == "int"
    assert annotations_to_type_str(EMPTY) == "str"


def test_function_annotation():
    def f(x: int, y: float, z: str) -> int:
        pass

    def g(x: int, y: int, x2: int) -> float:
        pass

    assert annotations_to_type_str(f) == "int -> float -> str -> int"
    assert annotations_to_type_str(g) == "int -> int -> int -> float"


def test_custom_types_annotation():
    class ClassA:
        pass

    class ClassB:
        pass

    def f(x: int, y: ClassA, z: str) -> ClassB:
        pass

    def g(x: ClassA, y: ClassB, x2: ClassA) -> ClassB:
        pass

    assert annotations_to_type_str(f) == "int -> ClassA -> str -> ClassB"
    assert annotations_to_type_str(g) == "ClassA -> ClassB -> ClassA -> ClassB"


def test_return_type():
    assert return_type("a -> b") == "b"
    assert return_type("a -> b -> c") == "c"
    assert return_type("a -> b -> c | d") == "c | d"


def test_arguments():
    assert arguments("a -> b") == ("a",)
    assert arguments("a -> b -> c") == ("a", "b")
    assert arguments("a -> b -> c | d") == ("a", "b")


def test_all_variants():
    assert all_variants("a -> b") == ["a->b"]
    assert all_variants("a -> b | c") == ["a->b", "a->c"]
    assert all_variants("'a [b|c] -> 'a -> c") == ["b->b->c", "c->c->c"]
