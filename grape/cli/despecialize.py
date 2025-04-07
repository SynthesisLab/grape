import argparse
from grape.automaton.automaton_manager import (
    dump_automaton_to_file,
    load_automaton_from_file,
)
from grape.automaton.spec_manager import despecialize


def parse_args():
    parser = argparse.ArgumentParser(
        description="Despecialize a grammar from a type request",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "automaton",
        type=str,
        help="your automaton file",
    )
    parser.add_argument(
        "type_request", type=str, help="type request the grammar was specialized to"
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
    grammar = despecialize(dfta, args.type_request)
    dump_automaton_to_file(grammar, args.output)


if __name__ == "__main__":
    main()
