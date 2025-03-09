from gpoe.enumerator import Enumerator
from gpoe.evaluator import Evaluator
from gpoe.program import Program
from gpoe.automaton_generator import grammar_from_type_constraints

from tqdm import tqdm


def __type_split__(type_str: str) -> tuple[str, ...]:
    return tuple(map(lambda x: x.strip(), type_str.strip().split("->")))


def find_regular_constraints(
    dsl: dict[str, tuple[str, callable]], evaluator: Evaluator, max_size: int
) -> list[tuple[Program, Program, str]]:
    constraints = []
    # Find all type requests
    all_types_req: set[str] = set()
    for str_type, _ in dsl.values():
        if "->" in str_type:
            all_types_req.add(str_type)

    all_pruned = set()

    # Generate all programs until some size
    pbar = tqdm(total=len(all_types_req))
    pbar.set_description_str("regular constraints")
    for type_req in all_types_req:
        pbar.set_postfix_str(type_req)
        nargs = len(type_req.split("->")) - 1
        grammar = grammar_from_type_constraints(dsl, type_req)
        gen = Enumerator(grammar, all_pruned).enumerate_until_size(max_size + 1)
        program = next(gen)
        evaluator.eval(program, type_req)
        should_keep = True
        try:
            while True:
                program = gen.send(should_keep)
                same_used, var_used = program.same_var_used_more_than_once()
                if same_used:
                    should_keep = False
                elif 0 not in var_used or len(var_used) != nargs:
                    should_keep = True
                else:
                    representative = evaluator.eval(program, type_req)
                    should_keep = representative is None
                    if not should_keep:
                        constraints.append((program, representative, type_req))
                        all_pruned.add(program)
        except StopIteration:
            pass
        pbar.update()
    pbar.close()
    return constraints
