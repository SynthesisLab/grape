import argparse
from grape.automaton.automaton_manager import load_automaton_from_file
from grape.automaton.spec_manager import specialize
from grape.cli import dsl_loader


def parse_args():
    parser = argparse.ArgumentParser(
        description="Count the number of programs at the specified constraints",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "automaton",
        type=str,
        help="your automaton file",
    )
    parser.add_argument(
        "--size", type=int, default=7, help="max size of programs to check"
    )
    parser.add_argument(
        "-r",
        "--request",
        type=str,
        default="None",
        required=False,
        help="specialized type request",
    )
    parser.add_argument(
        "--dsl",
        type=str,
        default=None,
        help="DSL file, enables pruning of finals states",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dfta = load_automaton_from_file(args.automaton)
    dsl = dsl_loader.load_python_file(args.dsl)[0] if args.dsl is not None else None
    if str(args.request) != "None":
        dfta = specialize(dfta, args.request, dsl)
        dfta.reduce()
    size = int(args.size)
    counts = dfta.trees_by_size(size)
    for size in sorted(counts):
        count = counts[size]
        print(f"size {size}: {count:.2e}")


if __name__ == "__main__":
    main()
