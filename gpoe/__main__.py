import argparse
import sys
from typing import Tuple
from tqdm import tqdm
from gpoe.approximate_constraint_finder import find_approximate_constraints
from gpoe.evaluator import Evaluator
from gpoe.regular_constraint_finder import find_regular_constraints
from gpoe.import_utils import import_file_function


def sample_inputs(
    nsamples: int, sample_dict: dict[str, callable], equal_dict: dict[str, callable]
) -> dict[str, list]:
    inputs = {}
    pbar = tqdm(total=nsamples * len(sample_dict))
    pbar.set_description_str("sampling")
    for sampled_type, sample_fn in sample_dict.items():
        pbar.set_postfix_str(sampled_type)
        eq_fn = equal_dict.get(sampled_type, lambda x, y: x == y)
        sampled_inputs = []
        tries = 0
        while len(sampled_inputs) < nsamples and tries < 100:
            sampled = sample_fn()
            if all(not eq_fn(sampled, el) for el in sampled_inputs):
                sampled_inputs.append(sampled)
                pbar.update()
                tries = 0
            tries += 1
        while len(sampled_inputs) < nsamples:
            before = len(sampled_inputs)
            sampled_inputs += sampled_inputs
            sampled_inputs = sampled_inputs[:nsamples]
            pbar.update(len(sampled_inputs) - before)

        inputs[sampled_type] = sampled_inputs
    pbar.close()
    return inputs


def load_file(
    file_path: str,
) -> Tuple[
    dict[str, Tuple[str, callable]],
    str | None,
    dict[str, callable],
    dict[str, callable],
    set,
]:
    space = import_file_function(
        file_path[:-3],
        ["dsl", "sample_dict", "equal_dict", "target_type", "skip_exceptions"],
    )()
    equal_dict = getattr(space, "equal_dict", dict())
    skip_exceptions = getattr(space, "skip_exceptions", set())

    return (
        {k: v for k, v in sorted(space.dsl.items())},
        getattr(space, "target_type", None),
        space.sample_dict,
        equal_dict,
        skip_exceptions,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Grammar Pruning with Observational Equivalence",
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
        "--size", type=int, default=7, help="max size of programs to check"
    )
    parser.add_argument(
        "--samples", type=int, default=1000, help="number of inputs to sample"
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="./grammar.txt",
        help="output file containing the pruned grammar",
    )
    parser.add_argument(
        "--allowed",
        type=str,
        default="./allowed.csv",
        help="output file containing only semantically unique programs",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="try to further reduce the number of programs. this is very slow and on average offers no or small gains",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    dsl, target_type, sample_dict, equal_dict, skip_exceptions = load_file(args.dsl)
    inputs = sample_inputs(args.samples, sample_dict, equal_dict)
    evaluator = Evaluator(dsl, inputs, equal_dict, skip_exceptions)
    approx_constraints = find_approximate_constraints(dsl, evaluator)
    grammar, allowed = find_regular_constraints(
        dsl, evaluator, args.size, target_type, approx_constraints, args.optimize
    )
    with open(args.allowed, "w") as fd:
        fd.write("program,type_request\n")
        for program, type_req in allowed:
            fd.write(f"{program},{type_req}\n")

    missing = set(dsl.keys()).difference(set(map(str, grammar.alphabet)))
    if missing:
        print(
            f"[warning] the following primitives are not present in the grammar: {', '.join(missing)}",
            file=sys.stderr,
        )

    # Save DFTA
    with open(args.output, "w") as fd:
        fd.write(repr(grammar))


if __name__ == "__main__":
    main()
