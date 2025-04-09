import argparse
from grape import types
from grape.automaton.automaton_manager import dump_automaton_to_file
from grape.automaton_generator import (
    depth_constraint,
    grammar_by_saturation,
    size_constraint,
)
from grape.cli import dsl_loader
from grape.program import Primitive, Variable


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a basic grammar based on type constraints",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    def is_python_file(file_path: str) -> bool:
        if not file_path.endswith(".py"):
            raise argparse.ArgumentTypeError("Only Python (.py) files are allowed.")
        return file_path

    parser.add_argument(
        "dsl",
        type=is_python_file,
        help="your python file defining your Domain Specific Language",
    )
    parser.add_argument(
        "--msize",
        type=int,
        default=-1,
        help="min size of programs to generate, -1 for infinite",
    )
    parser.add_argument(
        "--Msize",
        type=int,
        default=-1,
        help="max size of programs to generate, -1 for infinite",
    )
    parser.add_argument(
        "--mdepth",
        type=int,
        default=-1,
        help="min depth of programs to generate, -1 for infinite",
    )
    parser.add_argument(
        "--Mdepth",
        type=int,
        default=-1,
        help="max depth of programs to generate, -1 for infinite",
    )
    parser.add_argument("--short", action="store_true", help="state are renamed to SXX")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="./grammar.grape",
        help="output file containing the pruned grammar",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    dsl, target_type, sample_dict, _, __ = dsl_loader.load_python_file(args.dsl)
    type_req = "->".join(list(sample_dict.keys()) + [target_type])
    constraints = []
    mappers = []
    if int(args.msize) > 0 or int(args.Msize) > 0:
        constraints.append(
            size_constraint(min_size=int(args.msize), max_size=int(args.Msize))
        )
        mappers.append(lambda s: f"-size={s}")
    if int(args.mdepth) > 0 or int(args.Mdepth) > 0:
        constraints.append(
            depth_constraint(min_depth=int(args.mdepth), max_depth=int(args.Mdepth))
        )
        mappers.append(lambda s: f"-depth={s}")
    grammar = grammar_by_saturation(dsl, type_req, constraints)
    if not args.short:
        if len(constraints) == 0:
            grammar = grammar.map_states(lambda state: state[0])
        else:
            grammar = grammar.map_states(
                lambda state: state[0]
                + "".join([mappers[i](state[1][i]) for i in range(len(mappers))])
            )
    else:
        grammar = grammar.classic_state_renaming()
    types.check_automaton(grammar, dsl, type_req)
    args_type = types.arguments(type_req)
    grammar = grammar.map_alphabet(
        lambda x: Primitive(f"var_{args_type[x.no]}") if isinstance(x, Variable) else x
    )
    dsl.check_all_variants_present(grammar)
    grammar = dsl.merge_type_variants(grammar)
    dsl.check_all_primitives_present(grammar)

    dump_automaton_to_file(grammar, args.output)


if __name__ == "__main__":
    main()
