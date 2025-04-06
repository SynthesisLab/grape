import argparse
from grape.automaton.automaton_manager import (
    dump_automaton_to_file,
    load_automaton_from_file,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert a grammar to another format",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "automaton",
        type=str,
        help="your automaton file",
    )
    parser.add_argument(
        "output",
        type=str,
        help="output file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dfta = load_automaton_from_file(args.automaton)
    dump_automaton_to_file(dfta, args.output)


if __name__ == "__main__":
    main()
