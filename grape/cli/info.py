import argparse
from grape.automaton import spec_manager
from grape.automaton.automaton_manager import (
    load_automaton_from_file,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Show basic information about the grammar",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "automaton",
        type=str,
        help="your automaton file",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dfta = load_automaton_from_file(args.automaton)
    old_rules = dfta.rules.copy()
    dfta.reduce()

    specialized = spec_manager.is_specialized(dfta)

    print("terminals:", len(dfta.alphabet))
    print("states:", len(dfta.all_states))
    print("max arity:", dfta.max_arity())
    print("rules:", dfta.size())
    print("symbols:", dfta.symbols())
    print("reduced:", old_rules == dfta.rules)
    print("specialied:", specialized)
    if not dfta.is_unbounded():
        size, depth = dfta.compute_max_size_and_depth()
        print("max program size:", size)
        print("max program depth:", depth)
    else:
        print("unbounded programs:", dfta.is_unbounded())


if __name__ == "__main__":
    main()
