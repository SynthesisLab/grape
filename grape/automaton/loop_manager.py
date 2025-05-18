import itertools

from grape import types
from grape.automaton import spec_manager
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
) -> bool:
    if __state2letter__(candidate) != __state2letter__(original) and not str(
        __state2letter__(candidate)
    ).startswith("var"):
        return False
    for P1, args1 in reversed_rules[original]:
        has_equivalent = False
        for P2, args2 in reversed_rules[candidate]:
            if all(
                __can_states_merge(reversed_rules, arg1, arg2)
                for arg1, arg2 in zip(args1, args2)
            ):
                has_equivalent = True
                break
        if not has_equivalent:
            return False
    return True


def __find_merge__(
    dfta: DFTA[str, str], P: str, args: tuple[str, ...], candidates: set[str]
) -> str | None:
    best_candidate = None
    for candidate in candidates:
        if __state2letter__(candidate) != P and not str(
            __state2letter__(candidate)
        ).startswith("var"):
            continue
        has_equivalent = False
        for P2, args2 in dfta.reversed_rules[candidate]:
            if all(
                __can_states_merge(dfta.reversed_rules, arg1, arg2)
                for arg1, arg2 in zip(args, args2)
            ):
                has_equivalent = True
                break
        if has_equivalent and (
            best_candidate is None or best_candidate.count(" ") < candidate.count(" ")
        ):
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
        type_request = spec_manager.type_request_from_specialized(dfta, dsl)
        target_type = types.return_type(type_request)
        whatever = target_type == "none"
        state_to_type = dsl.get_state_types(dfta)
        state_to_size = {s: s.count(" ") for s in dfta.all_states}
        max_size = max(state_to_size.values())
        states_by_types = {
            t: set(s for s, st in state_to_type.items() if st == t)
            for t in set(state_to_type.values())
        }
        added = True
        new_dfta = DFTA(dfta.rules.copy(), dfta.finals.copy())
        virtual_vars = set()
        max_varno = (
            max(
                int(s[len("var") :])
                for s in state_to_type.keys()
                if s.startswith("var")
            )
            + 1
        )
        for t, states in states_by_types.copy().items():
            if all(not s.startswith("var") for s in states):
                virtual_vars.add(max_varno)
                dst = str(Variable(max_varno))
                new_dfta.rules[(Variable(max_varno), tuple())] = dst
                states_by_types[t].add(dst)
                state_to_size[dst] = 1
                max_varno += 1
        new_dfta.refresh_reversed_rules()
        while added:
            added = False
            for P, (Ptype, _) in dsl.primitives.items():
                possibles = [states_by_types[arg_t] for arg_t in types.arguments(Ptype)]
                for combi in itertools.product(*possibles):
                    key = (P, combi)
                    if key not in new_dfta.rules:
                        args_size = list(map(lambda x: state_to_size[x], combi))
                        dst_size = sum(args_size) + 1
                        if (
                            dst_size >= max_size
                            and max(args_size) >= max_size - len(args_size) + 1
                        ):
                            added = True
                            rtype = types.return_type(dsl.get_type(P))
                            dst = Function(Primitive(P), list(map(Primitive, combi)))
                            new_state = __find_merge__(
                                new_dfta, P, combi, states_by_types[rtype]
                            ) or str(dst)
                            new_dfta.rules[key] = new_state
                            states_by_types[rtype].add(new_state)
                            if new_state not in state_to_size:
                                # This is a new state to the automaton (no merge)
                                state_to_size[new_state] = dst_size
                                # Should it be final?
                                if whatever or rtype == target_type:
                                    new_dfta.finals.add(new_state)
            new_dfta.refresh_reversed_rules()

    for no in virtual_vars:
        dst = Variable(no)
        del new_dfta.rules[(dst, tuple())]
    new_dfta.reduce()
    new_dfta.refresh_reversed_rules()
    return __convert_automaton__(new_dfta)  # .minimise())#.classic_state_renaming())
