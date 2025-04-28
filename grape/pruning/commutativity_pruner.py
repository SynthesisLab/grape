from typing import Generator, TypeVar
from grape.dsl import DSL
from grape.evaluator import Evaluator
from grape.program import Function, Primitive, Program, Variable
import grape.types as types

T = TypeVar("T")


def __produce_all_variants__(
    possibles: list[list[T]],
) -> Generator[list[T], None, None]:
    # Note to self: what is the difference between this and itertools.product?
    # Enumerate all combinations
    n = len(possibles)
    maxi = [len(possibles[i]) for i in range(n)]
    current = [0 for _ in range(n)]
    while current[0] < maxi[0]:
        yield [possibles[i][j] for i, j in enumerate(current)]
        # Next combination
        i = n - 1
        current[i] += 1
        while i > 0 and current[i] >= maxi[i]:
            current[i] = 0
            i -= 1
            current[i] += 1


def get_rewrites(
    dsl: DSL, primitive: str, swapped_indices: tuple[int, int]
) -> list[tuple[Program, Program, str]]:
    constraints: list[tuple[Program, Program, str]] = []
    stype = dsl[primitive][0]
    args_type, _ = types.parse(stype)
    swapped_type = args_type[swapped_indices[0]]

    nargs = len(types.arguments(dsl.primitives[primitive]))

    for p1, (stype1, _) in dsl.primitives.copy().items():
        args1, rtype1 = types.parse(stype1)
        if rtype1 != swapped_type:
            continue
        nargs1 = len(args1)
        first_arg = (
            Function(Primitive(p1), [Variable(i + nargs) for i in range(nargs1)])
            if nargs1 > 0
            else Primitive(p1)
        )

        for p2, (stype2, _) in dsl.primitives.items():
            if p1 >= p2:
                continue
            args2, rtype2 = types.parse(stype2)
            if rtype2 != swapped_type:
                continue

            second_arg: Program = (
                Function(
                    Primitive(p2),
                    [Variable(i + nargs + nargs1) for i in range(len(args2))],
                )
                if len(args2) > 0
                else Primitive(p2)
            )
            # Valid pair that we have to forbid
            deleted = Function(
                Primitive(primitive), [Variable(i) for i in range(nargs)]
            )
            deleted.arguments[swapped_indices[0]] = first_arg
            deleted.arguments[swapped_indices[1]] = second_arg
            equiv_to = Function(
                Primitive(primitive), [Variable(i) for i in range(nargs)]
            )
            equiv_to.arguments[swapped_indices[0]] = second_arg
            equiv_to.arguments[swapped_indices[1]] = first_arg
            constraints.append((deleted, equiv_to))
        # Add additional constraint for variable type

        second_arg = Variable(swapped_indices[0])
        # Valid pair that we have to forbid
        deleted = Function(Primitive(primitive), [Variable(i) for i in range(nargs)])
        deleted.arguments[swapped_indices[0]] = first_arg
        deleted.arguments[swapped_indices[1]] = second_arg
        equiv_to = Function(Primitive(primitive), [Variable(i) for i in range(nargs)])
        equiv_to.arguments[swapped_indices[0]] = second_arg
        equiv_to.arguments[swapped_indices[1]] = first_arg
        constraints.append((deleted, equiv_to))

    return constraints


def prune(
    dsl: DSL,
    evaluator: Evaluator,
) -> list[tuple[str, list[int]]]:
    commutatives = []
    for prim, (stype, _) in dsl.primitives.items():
        args = types.arguments(stype)
        if len(args) < 2:
            continue
        # Check if we can sample all elements
        if any(t not in evaluator.base_inputs for t in args):
            continue
        base_program = Function(
            Primitive(prim), [Variable(i) for i in range(len(args))]
        )
        evaluator.eval(base_program, stype)
        # Find same type variables
        args_per_type: dict[str, list[Variable]] = {}
        for i, arg_type in enumerate(args):
            if arg_type not in args_per_type:
                args_per_type[arg_type] = []
            args_per_type[arg_type].append(Variable(i))
        for new_args in __produce_all_variants__([args_per_type[t] for t in args]):
            nswaps = sum(x.no != i for i, x in enumerate(new_args))
            if nswaps != 2:
                continue
            variant = Function(Primitive(prim), new_args)
            if evaluator.eval(variant, stype) is not None:
                commutatives.append(
                    (prim, [i for i, x in enumerate(new_args) if x.no != i])
                )
    evaluator.clean_memoisation()
    return commutatives
