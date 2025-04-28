import argparse
from grape.automaton.automaton_manager import (
    dump_automaton_to_file,
    load_automaton_from_file,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Produces the union of multiple grammars",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "grammars",
        type=str,
        nargs="+",
        help="your grammar files",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="output file",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    grammars = [load_automaton_from_file(file) for file in args.grammars]
    out = grammars.pop()
    while grammars:
        out = out.read_union(grammars.pop())
        out.reduce()
        out = out.minimise()
    out = out.classic_state_renaming()
    dump_automaton_to_file(out, args.output)


if __name__ == "__main__":
    main()
