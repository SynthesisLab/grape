import argparse
from grape.automaton.automaton_manager import load_automaton_from_file
from grape.enumerator import Enumerator


def parse_args():
    parser = argparse.ArgumentParser(
        description="Enumerate all programs until some size",
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

    enumerator = Enumerator(dfta)
    gen = enumerator.enumerate_until_size(args.size + 1)
    next(gen)
    try:
        while True:
            print(gen.send(True))
    except StopIteration:
        pass


if __name__ == "__main__":
    main()
