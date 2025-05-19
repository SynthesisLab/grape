import itertools

from grape import types
from grape.automaton.tree_automaton import DFTA
from grape.dsl import DSL
from grape.program import Function, Primitive, Program, Variable


def __state2letter__(state: str) -> str:
    if "(" in state:
        return state[1 : state.find(" ")]
    else:
        return state


def __can_states_merge(
    reversed_rules: dict[tuple[str, tuple[str, ...]], str],
    original: str,
    candidate: str,
    merge_memory: dict[(str, str), bool],
    state_to_letter: dict[str, tuple[str, bool]],
) -> bool:
    res = merge_memory.get((original, candidate))
    if res is None:
        lc = state_to_letter[candidate]
        if lc[0] != state_to_letter[original][0] and not lc[1]:
            merge_memory[(original, candidate)] = False
            merge_memory[(candidate, original)] = False
            return False
        for P1, args1 in reversed_rules[original]:
            has_equivalent = False
            for P2, args2 in reversed_rules[candidate]:
                if all(
                    __can_states_merge(
                        reversed_rules, arg1, arg2, merge_memory, state_to_letter
                    )
                    for arg1, arg2 in zip(args1, args2)
                    if arg1 != arg2
                ):
                    has_equivalent = True
                    break
            if not has_equivalent:
                merge_memory[(original, candidate)] = False
                merge_memory[(candidate, original)] = False
                return False
        merge_memory[(original, candidate)] = True
        merge_memory[(candidate, original)] = True
        return True
    else:
        return res


def __find_merge__(
    dfta: DFTA[str, str],
    P: str,
    args: tuple[str, ...],
    candidates: set[str],
    merge_memory: dict[(str, str), bool],
    state_to_letter: dict[str, tuple[str, bool]],
    state_to_size: dict[str, int],
) -> str | None:
    best_candidate = None
    size_best = -1
    for candidate in candidates:
        if state_to_size[candidate] <= size_best:
            break
        elif state_to_letter[candidate][0] != P and not state_to_letter[candidate][1]:
            continue
        has_equivalent = False
        for P2, args2 in dfta.reversed_rules[candidate]:
            if all(
                __can_states_merge(
                    dfta.reversed_rules, arg1, arg2, merge_memory, state_to_letter
                )
                for arg1, arg2 in zip(args, args2)
                if arg1 != arg2
            ):
                has_equivalent = True
                break

        if has_equivalent and (
            best_candidate is None or size_best < state_to_size[candidate]
        ):
            size_best = state_to_size[candidate]
            best_candidate = candidate
    return best_candidate


def __convert_automaton__(dfta: DFTA[str, str]) -> DFTA[str, Program]:
    return dfta.map_alphabet(
        lambda x: Variable(int(str(x)[len("var") :]))
        if str(x).startswith("var")
        else Primitive(str(x))
    )


def add_loops(
    dfta: DFTA[str, Program | str],
    dsl: DSL,
) -> DFTA[str, Program]:
    """
    Assumes specialized DFTA, one state = one letter and that variants are mapped.
    """
    if dfta.is_unbounded():
        raise ValueError("automaton is already looping: cannot add loops!")
    else:
        state_to_type = dsl.get_state_types(dfta)
        state_to_size = {s: s.count(" ") + 1 for s in dfta.all_states}
        state_to_letter = {
            s: (__state2letter__(s), __state2letter__(s).startswith("var"))
            for s in dfta.all_states
        }
        max_size = max(state_to_size.values())
        states_by_types = {
            t: sorted(
                [s for s, st in state_to_type.items() if st == t],
                reverse=True,
                key=lambda s: state_to_size[s],
            )
            for t in set(state_to_type.values())
        }
        new_dfta = DFTA(dfta.rules.copy(), dfta.finals.copy())
        virtual_vars = set()
        max_varno = (
            max(
                int(s[len("var") :])
                for s in state_to_type.keys()
                if state_to_letter[s][1]
            )
            + 1
        )
        for t, states in states_by_types.copy().items():
            if all(not state_to_letter[s][1] for s in states):
                virtual_vars.add(max_varno)
                dst = str(Variable(max_varno))
                new_dfta.rules[(Variable(max_varno), tuple())] = dst
                states_by_types[t].append(dst)
                state_to_size[dst] = 1
                state_to_letter[dst] = (dst, True)
                max_varno += 1
        new_dfta.refresh_reversed_rules()
        merge_memory = {}
        for P, (Ptype, _) in dsl.primitives.items():
            rtype = types.return_type(Ptype)
            possibles = [states_by_types[arg_t] for arg_t in types.arguments(Ptype)]
            for combi in itertools.product(*possibles):
                key = (P, combi)
                if key not in new_dfta.rules:
                    dst_size = sum(map(lambda x: state_to_size[x], combi)) + 1
                    if dst_size > max_size:
                        dst = Function(Primitive(P), list(map(Primitive, combi)))
                        new_state = __find_merge__(
                            new_dfta,
                            P,
                            combi,
                            states_by_types[rtype],
                            merge_memory,
                            state_to_letter,
                            state_to_size,
                        ) or str(dst)
                        new_dfta.rules[key] = new_state
                        assert new_state in state_to_size

    for no in virtual_vars:
        dst = Variable(no)
        del new_dfta.rules[(dst, tuple())]
    new_dfta.reduce()
    return __convert_automaton__(new_dfta).minimise().classic_state_renaming()
