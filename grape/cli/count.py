import argparse
from grape.automaton.automaton_manager import load_automaton_from_file


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
    return parser.parse_args()


def main():
    args = parse_args()
    dfta = load_automaton_from_file(args.automaton)
    size = int(args.size)
    counts = dfta.trees_by_size(size)
    for size in sorted(counts):
        count = counts[size]
        print(f"size {size}: {count:.2e}")


if __name__ == "__main__":
    main()
