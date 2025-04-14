from collections import defaultdict
from enum import StrEnum
import itertools

from grape.automaton.tree_automaton import DFTA
from grape.dsl import DSL


class LoopStrategy(StrEnum):
    NO_LOOP = "none"
    STATE = "state"


def __find_unbounded_types(
    dfta: DFTA[str, str], state_to_type: dict[str, str]
) -> set[str]:
    unbounded_types = set()
    added = True
    while added:
        added = False
        for (P, args), dst in dfta.rules.items():
            prod_type = state_to_type[dst]
            if prod_type not in unbounded_types and any(
                state_to_type[arg_state] in unbounded_types
                or prod_type == state_to_type[arg_state]
                for arg_state in args
            ):
                unbounded_types.add(prod_type)
                added = True
    return unbounded_types


def __find_unconsumed_states(dfta: DFTA[str, str]) -> set[str]:
    not_consumed = dfta.all_states
    for P, args in dfta.rules:
        for arg_state in args:
            if arg_state in not_consumed:
                not_consumed.remove(arg_state)
    return not_consumed


def __prod_types_by_states(
    dfta: DFTA[str, str], state_to_type: dict[str, str]
) -> dict[str, set[str]]:
    # Compute transitive closure
    reachable_from: dict[str, set[str]] = defaultdict(set)
    for (P, args), dst in dfta.rules.items():
        reachable_from[dst].update(args)
    updated = True
    while updated:
        updated = False
        for dst, reachables in reachable_from.copy().items():
            before = len(reachables)
            for S in reachables.copy():
                reachables.update(reachable_from[S])
            if len(reachables) != before:
                updated = True
    return {
        s: set(state_to_type[v] for v in reachables)
        for s, reachables in reachable_from.items()
    }


def __compute_outbound(dfta: DFTA[str, str], unconsumed: set[str]) -> dict[str, int]:
    outbound: dict[str, int] = {}
    for x in unconsumed:
        outbound[x] = 1
    queue = list(dfta.all_states)
    while queue:
        x = queue.pop()
        if x in outbound:
            continue
        total = 0
        has_missed = False
        for (P, args), dst in dfta.rules.items():
            if x in args:
                if dst not in outbound:
                    has_missed = True
                    break
                else:
                    total += outbound[dst]
        if has_missed:
            queue.insert(0, x)
        else:
            outbound[x] = total
    return outbound


def __can_states_merge(
    dfta: DFTA[str, str], state_to_letter: dict[str, str], original: str, candidate: str
) -> bool:
    if state_to_letter[candidate] != state_to_letter[original] and not str(
        state_to_letter[candidate]
    ).startswith("var"):
        return False
    for P1, args1 in dfta.reversed_rules[original]:
        has_equivalent = False
        for P2, args2 in dfta.reversed_rules[candidate]:
            if all(
                __can_states_merge(dfta, state_to_letter, arg1, arg2)
                for arg1, arg2 in zip(args1, args2)
            ):
                has_equivalent = True
                break
        if not has_equivalent:
            return False
    return True


def add_loops(
    dfta: DFTA[str, str],
    dsl: DSL,
    strategy: LoopStrategy,
    type_request: str | None = None,
) -> DFTA[str, str]:
    """
    Assumes one state is from one letter
    """
    if strategy == LoopStrategy.NO_LOOP:
        return dfta
    elif dfta.is_unbounded():
        raise ValueError("automaton is already looping cannot add loops!")
    else:
        # In order to make the automaton loop
        # 1) All unconsumed must be consumed
        # 2) Programs of all produced types must have unbounded size
        state_to_type = dsl.get_state_types(dfta, type_request)
        state_to_letter = {s: dfta.reversed_rules[s][0][0] for s in state_to_type}
        prod_types_by_state = __prod_types_by_states(dfta, state_to_type)
        all_types = set(state_to_type.values())
        unbounded_types = __find_unbounded_types(dfta, state_to_type)
        unconsumed = __find_unconsumed_states(dfta)
        unconsumed_by_type = {
            t: {s for s in unconsumed if state_to_type[s] == t} for t in all_types
        }
        unbounded_unconsumed = {
            t for t in unbounded_types if t not in unconsumed_by_type
        }
        # For each unbounded unconsumed
        #   find all states that are not consumed to produce more of that type
        #       mark them as unconsumed
        for t in unbounded_unconsumed:
            unconsumed_by_type[t] = set()
            for state in dfta.all_states:
                if state_to_type[state] == t and t not in prod_types_by_state[state]:
                    unconsumed.add(state)
                    unconsumed_by_type[t].add(state)
        # Computes consumed
        consumed = dfta.all_states.difference(unconsumed)
        consumed_by_type = {
            t: {s for s in consumed if state_to_type[s] == t} for t in all_types
        }
        outbound = __compute_outbound(dfta, unconsumed)
        state_merged: dict[str, str] = {}
        new_rules = dfta.rules.copy()
        new_finals = dfta.finals.copy()
        # 1) Merge all unconsumed onto the largest subcontext that is being consumed
        unmerged_by_type: dict[str, set[str]] = defaultdict(set)
        for t, states in unconsumed_by_type.items():
            for state in states:
                has_merge = False
                for candidate in consumed_by_type[t]:
                    if not __can_states_merge(dfta, state_to_letter, state, candidate):
                        continue
                    if (
                        has_merge
                        and outbound[candidate] < outbound[state_merged[state]]
                    ) or not has_merge:
                        state_merged[state] = candidate
                    has_merge = True
                if not has_merge:
                    unmerged_by_type[t].add(state)
        if strategy == LoopStrategy.STATE:
            for (P, args), dst in dfta.rules.items():
                if dst in state_merged:
                    new_rules[(P, args)] = state_merged[dst]
        else:
            assert False, f"unsupported loop strategy:{strategy}"
        # 2) Some can still be unmerged
        # this means multiple things:
        # - there is no variable of that type
        # - there is not smaller expression using the same letter
        # print(
        #     "UNMERGED:\n",
        #     "\n".join([f"\t{k} ====> {v}" for k, v in unmerged_by_type.items()]),
        # )
        for (P, args), dst in dfta.rules.items():
            possibles = [[arg] for arg in args]
            added = False
            for rtype, programs in unmerged_by_type.items():
                for li in possibles:
                    if state_to_type[li[0]] != rtype:
                        continue
                    else:
                        added = True
                        li.extend(programs)
            if added:
                for new_args in itertools.product(*possibles):
                    new_rules[(P, new_args)] = dst
        new_dfta = DFTA(new_rules, new_finals)
        new_dfta.reduce()
        out = new_dfta.minimise(
            can_be_merged=lambda x, y: state_to_type[x] == state_to_type[y]
        ).classic_state_renaming()
        return out
