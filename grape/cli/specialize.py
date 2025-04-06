import argparse
from grape.automaton.automaton_manager import (
    dump_automaton_to_file,
    load_automaton_from_file,
)
from grape.automaton.spec_manager import specialize
from grape.cli import dsl_loader


def parse_args():
    parser = argparse.ArgumentParser(
        description="Specialize a grammar to a type request",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "automaton",
        type=str,
        help="your automaton file",
    )
    parser.add_argument(
        "type_request", type=str, help="type request to specialize the grammar to"
    )
    parser.add_argument(
        "--dsl",
        type=str,
        default=None,
        help="DSL file, enables pruning of finals states",
    )
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
    dfta = load_automaton_from_file(args.automaton)
    dsl = dsl_loader.load_python_file(args.dsl)[0] if args.dsl is not None else None
    grammar = specialize(dfta, args.type_request, dsl)
    grammar.reduce()
    dump_automaton_to_file(grammar, args.output)


if __name__ == "__main__":
    main()
