import argparse
from tqdm import tqdm
from grape import types
from grape.automaton.automaton_manager import dump_automaton_to_file
from grape.cli import dsl_loader
from grape.pruning.approximate_constraint_finder import find_approximate_constraints
from grape.evaluator import Evaluator
from grape.pruning.regular_constraint_finder import find_regular_constraints


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
        default="./grammar.grape",
        help="output file containing the pruned grammar",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="try to further reduce the number of programs. this is very slow and on average offers no or small gains",
    )
    parser.add_argument(
        "--no-loop",
        action="store_true",
        help="the grammar will produce programs only up to the size specified",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    dsl, target_type, sample_dict, equal_dict, skip_exceptions = (
        dsl_loader.load_python_file(args.dsl)
    )
    inputs = sample_inputs(args.samples, sample_dict, equal_dict)
    evaluator = Evaluator(dsl, inputs, equal_dict, skip_exceptions)
    approx_constraints = find_approximate_constraints(dsl, evaluator)
    grammar, allowed = find_regular_constraints(
        dsl,
        evaluator,
        args.size,
        target_type,
        approx_constraints,
        args.optimize,
        args.no_loop,
    )

    type_req = allowed[0][-1]
    types.check_automaton(grammar, dsl, type_req)
    dsl.check_all_variants_present(grammar)
    grammar = dsl.merge_type_variants(grammar)
    dsl.check_all_primitives_present(grammar)

    dump_automaton_to_file(grammar, args.output)


if __name__ == "__main__":
    main()
