from typing import Generator, TypeVar
from gpoe.evaluator import Evaluator
from gpoe.program import Function, Primitive, Program, Variable


def find_approximate_constraints(
    dsl: dict[str, tuple[str, callable]],
    evaluator: Evaluator,
) -> list[tuple[Program, Program, str]]:
    constraints = __find_commutativity__(dsl, evaluator)
    return constraints


def __type_split__(type_str: str) -> tuple[str, ...]:
    return tuple(map(lambda x: x.strip(), type_str.strip().split("->")))


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


def __add_commutative_constraints__(
    dsl: dict[str, tuple[str, callable]], primitive: str, args: list[Variable]
) -> list[tuple[Program, Program, str]]:
    constraints = []
    stype = dsl[primitive][0]
    btype = __type_split__(stype)
    args_type = btype[:-1]
    swapped_indices = [i for i, x in enumerate(args) if x.no != i]
    swapped_type = args_type[swapped_indices[0]]

    nargs = len(args)

    for p1, (stype1, _) in dsl.copy().items():
        btype1 = __type_split__(stype1)
        rtype1 = btype1[-1]
        if rtype1 != swapped_type:
            continue
        nargs1 = len(btype1) - 1
        first_arg = (
            Function(Primitive(p1), [Variable(i + nargs) for i in range(nargs1)])
            if len(btype1) > 1
            else Primitive(p1)
        )
        type_req1 = args_type + btype1[:-1]

        for p2, (stype2, _) in dsl.items():
            if p1 >= p2:
                continue
            btype2 = __type_split__(stype2)
            rtype2 = btype2[-1]
            if rtype2 != swapped_type:
                continue
            type_req2 = type_req1 + btype2[:-1] + (btype[-1],)

            second_arg = (
                Function(
                    Primitive(p2),
                    [Variable(i + nargs + nargs1) for i in range(len(btype2) - 1)],
                )
                if len(btype2) > 1
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
            constraints.append((deleted, equiv_to, "->".join(type_req2)))
    return constraints


def __find_commutativity__(
    dsl: dict[str, tuple[str, callable]],
    evaluator: Evaluator,
) -> list[tuple[Program, Program, str]]:
    constraints = []
    for prim, (stype, _) in dsl.items():
        btype = __type_split__(stype)
        args = btype[:-1]
        if len(args) < 2:
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
                constraints += __add_commutative_constraints__(dsl, prim, new_args)
    return constraints
