from collections import defaultdict
from typing import (
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
    overload,
)
import itertools
from grape.partitions import integer_partitions

U = TypeVar("U")
V = TypeVar("V")
W = TypeVar("W")
X = TypeVar("X")


class DFTA(Generic[U, V]):
    """
    Deterministic finite tree automaton.
    states: U
    alphabet: V
    """

    def __init__(
        self,
        rules: Dict[
            Tuple[
                V,
                Tuple[U, ...],
            ],
            U,
        ],
        finals: Set[U],
    ) -> None:
        self.finals = {s for s in sorted(finals)}
        self.rules = {k: rules[k] for k in sorted(rules, key=str)}
        self.reversed_rules: Dict[
            U,
            List[
                Tuple[
                    V,
                    Tuple[U, ...],
                ]
            ],
        ] = {}
        self.refresh_reversed_rules()

    def refresh_reversed_rules(self) -> None:
        self.reversed_rules = defaultdict(list)
        for r, s in self.rules.items():
            self.reversed_rules[s].append(r)

    def copy(self) -> "DFTA[U, V]":
        """Produces a shallow copy of this automaton."""
        return DFTA({k: v for k, v in self.rules.items()}, {s for s in self.finals})

    def size(self) -> int:
        """
        Return the size of the DFTA which is the number of rules.
        """
        return len(self.rules)

    @property
    def states(self) -> Set[U]:
        """
        The set of reachable states.
        """
        reachable = set()
        added = True
        rules = defaultdict(list)
        for (_, args), dst in self.rules.items():
            rules[dst].append(args)
        while added:
            added = False
            for dst in list(rules.keys()):
                for args in rules[dst]:
                    if all(s in reachable for s in args):
                        reachable.add(dst)
                        added = True
                        del rules[dst]
                        break
        return reachable

    @property
    def all_states(self) -> Set[U]:
        """
        The set of all states.
        """
        reachable = set()
        for (_, args), dst in self.rules.items():
            reachable.add(dst)
            for arg in args:
                reachable.add(arg)
        return reachable

    @property
    def alphabet(self) -> Set[V]:
        """
        The set of letters.
        """
        alphabet = set()
        for (letter, _), __ in self.rules.items():
            alphabet.add(letter)
        return alphabet

    def read(self, letter: V, children: Tuple[U, ...]) -> Optional[U]:
        return self.rules.get((letter, children), None)

    def __remove_unreachable__(self) -> None:
        new_states = self.states
        new_rules = {
            (letter, args): dst
            for (letter, args), dst in self.rules.items()
            if dst in new_states and all(s in new_states for s in args)
        }
        self.rules = new_rules
        self.finals = self.finals.intersection(new_states)

    def __product_rules__(
        self, other: "DFTA[W, V]"
    ) -> Dict[
        Tuple[
            V,
            Tuple[tuple[U, W], ...],
        ],
        tuple[U, W],
    ]:
        new_rules: Dict[
            Tuple[
                V,
                Tuple[tuple[U, W], ...],
            ],
            tuple[U, W],
        ] = {}
        for (P1, args1), dst1 in self.rules.items():
            for (P2, args2), dst2 in other.rules.items():
                if P1 != P2 or len(args1) != len(args2):
                    continue
                new_args = tuple((a1, a2) for a1, a2 in zip(args1, args2))
                new_rules[(P1, new_args)] = (dst1, dst2)
        return new_rules

    def read_intersection(self, other: "DFTA[W, V]") -> "DFTA[tuple[U, W], V]":
        new_finals = set(el for el in itertools.product(self.finals, other.finals))
        d = DFTA(self.__product_rules__(other), new_finals)
        d.reduce()
        return d

    def read_union(self, other: "DFTA[W, V]") -> "DFTA[tuple[U, W], V]":
        new_finals = set(
            el for el in itertools.product(self.finals, other.states)
        ) | set(el for el in itertools.product(self.states, other.finals))
        d = DFTA(self.__product_rules__(other), new_finals)
        d.reduce()
        return d

    def __get_consumed__(self) -> Set[U]:
        consumed: Set[U] = {q for q in self.finals}
        new_elems = list(consumed)
        while new_elems:
            dst = new_elems.pop()
            for (_, args), pot_dst in self.rules.items():
                if dst == pot_dst:
                    for arg in args:
                        if arg not in consumed:
                            new_elems.append(arg)
                        consumed.add(arg)
        return consumed

    def __remove_unproductive__(self) -> None:
        removed = True
        while removed:
            removed = False
            consumed = self.__get_consumed__()
            for S, dst in list(self.rules.items()):
                if dst not in consumed:
                    del self.rules[S]
                    removed = True

    def reduce(self) -> None:
        """
        Removes unreachable states and unproductive states.
        """
        self.__remove_unreachable__()
        self.__remove_unproductive__()
        self.refresh_reversed_rules()

    @overload
    def minimise(
        self,
        mapping: Callable[[Tuple[U, ...]], W],
        can_be_merged: Callable[[U, U], bool] = lambda x, y: True,
    ) -> "DFTA[W, V]":
        pass

    @overload
    def minimise(
        self,
        mapping: Literal[None] = None,
        can_be_merged: Callable[[U, U], bool] = lambda x, y: True,
    ) -> "DFTA[Tuple[U, ...], V]":
        pass

    def minimise(
        self,
        mapping: Union[Literal[None], Callable[[Tuple[U, ...]], W]] = None,
        can_be_merged: Callable[[U, U], bool] = lambda x, y: True,
    ) -> "Union[DFTA[Tuple[U, ...], V], DFTA[W, V]]":
        """
        Assumes this is a reduced DTFA.
        Mapping is used to map states equivalence classes to new identifiers if given like map_states.

        Adapted algorithm from:
        Brainerd, Walter S.. “The Minimalization of Tree Automata.” Inf. Control. 13 (1968): 484-491.
        """
        # 1. Build consumer_of
        # state -> list of (letter, args), no_of_arg consuming state
        consumer_of: Dict[
            U,
            List[
                Tuple[
                    Tuple[
                        V,
                        Tuple[U, ...],
                    ],
                    int,
                ]
            ],
        ] = {q: [] for q in self.states}
        for l, args in self.rules:
            for k, ik in enumerate(args):
                consumer_of[ik].append(((l, args), k))
        # 2. Init equiv classes
        state2cls: Dict[U, int] = {q: int(q in self.finals) for q in self.states}
        cls2states: Dict[int, Tuple[U, ...]] = {
            j: tuple({q for q, i in state2cls.items() if i == j}) for j in [0, 1]
        }

        n = 1
        finished = False

        # Routines
        def are_equivalent(a: U, b: U) -> bool:
            """
            Check that two states are equivalent:

            all consumers of a, can also consume b at the same argument index and map to the same equivalent class
            and vice-versa
            """
            if not can_be_merged(a, b):
                return False
            for S, k in consumer_of[a]:
                P, args = S
                # Replacing a at index k with b
                newS = (P, tuple([p if j != k else b for j, p in enumerate(args)]))
                # Check that rules[S] and rules[newS] go into the same equi. class
                dst_cls = state2cls[self.rules[S]]
                out = self.rules.get(newS)
                if out is None or state2cls[out] != dst_cls:
                    return False
            # Symmetry with b
            for S, k in consumer_of[b]:
                P, args = S
                dst_cls = state2cls[self.rules[S]]
                newS = (P, tuple([p if j != k else a for j, p in enumerate(args)]))
                out = self.rules.get(newS)
                if out is None or state2cls[out] != dst_cls:
                    return False
            return True

        # 3. Main loop
        while not finished:
            finished = True
            # For each equivalence class
            for i in range(n + 1):
                cls = list(cls2states[i])
                # While there is something in the ith class
                while cls:
                    new_cls = []
                    representative = cls.pop()
                    new_cls.append(representative)
                    next_cls = []
                    # Build two classes:
                    #   - new: all states that are equivalent to representative
                    #   - next: all the other states
                    for q in cls:
                        if are_equivalent(representative, q):
                            new_cls.append(q)
                        else:
                            next_cls.append(q)
                    cls = next_cls
                    if len(cls) != 0:
                        # next becomes the new nth class

                        # Create new equivalence class
                        n += 1
                        for q in new_cls:
                            state2cls[q] = n
                        cls2states[n] = tuple(new_cls)
                        finished = False
                    else:
                        # No new class has been made so we can go to the next equivalence class (hence cls = [])
                        # new_cls (now) has NOT changed from cls (previous iter.), they are the same
                        # thus we just need to re-set it (because there might have been multiple iterations)
                        # i is a free slot since other classes are added at the end
                        cls2states[i] = tuple(new_cls)

        f = mapping or (lambda x: x)  # type: ignore
        new_rules = {}
        for (l, args), dst in self.rules.items():
            t_args = tuple([f(cls2states[state2cls[q]]) for q in args])
            new_rules[(l, t_args)] = f(cls2states[state2cls[dst]])
        return DFTA(new_rules, {f(cls2states[state2cls[q]]) for q in self.finals})  # type: ignore

    def map_states(self, mapping: Callable[[U], X]) -> "DFTA[X, V]":
        return DFTA(
            {
                (l, tuple(map(mapping, args))): mapping(dst)
                for (l, args), dst in self.rules.items()
            },
            set(map(mapping, self.finals)),
        )

    def classic_state_renaming(self) -> "DFTA[str, V]":
        """
        Rename states in the format SXX
        """
        mapping = {}

        def get_state(x):
            if x not in mapping:
                mapping[x] = f"S{len(mapping)}"
            return mapping[x]

        return self.map_states(get_state)

    def map_alphabet(self, mapping: Callable[[V], X]) -> "DFTA[U, X]":
        return DFTA(
            {(mapping(l), args): dst for (l, args), dst in self.rules.items()},
            self.finals.copy(),
        )

    def stream_trees_by_size(
        self, size: int, finals_only: bool = True
    ) -> Generator[tuple[int, int], None, None]:
        """
        Return the number of trees produced of all sizes until the given size (included).
        stream (size, number of trees)
        """

        states = self.states
        accepted = self.finals if finals_only else states
        count: dict[U, dict[int, int]] = {state: {} for state in states}
        for csize in range(1, size + 1):
            for state in states:
                count[state][csize] = 0
                for derivation in self.reversed_rules[state]:
                    _, args = derivation
                    if len(args) == 0 and csize == 1:
                        count[state][csize] += 1
                    elif len(args) > 0:
                        for partition in integer_partitions(len(args), csize - 1):
                            total = 1
                            for arg_size, arg in zip(partition, args):
                                total *= count[arg][arg_size]
                            count[state][csize] += total
            yield csize, sum(count[state][csize] for state in accepted)

    def trees_by_size(self, size: int, finals_only: bool = True) -> dict[int, int]:
        """
        Return the number of trees produced of all sizes until the given size (included).
        """
        return {
            size: count
            for size, count in self.stream_trees_by_size(size, finals_only=finals_only)
        }

    def trees_at_size(self, size: int, finals_only: bool = True) -> int:
        """
        Return the number of trees produced of exactly the given size.
        """
        return self.trees_by_size(size, finals_only=finals_only)[size]

    def trees_until_size(self, size: int, finals_only: bool = True) -> int:
        """
        Return the number of trees produced of the given size (included) or less.
        """
        return sum(self.trees_by_size(size, finals_only=finals_only).values())

    def max_arity(self) -> int:
        return max(len(args) for _, args in self.rules)

    def is_unbounded(self) -> bool:
        """
        Returns true if the grammar produces unbounded programs.
        """
        reachable_from: dict[U, set[V]] = defaultdict(set)
        for (P, args), dst in self.rules.items():
            reachable_from[dst].update(args)

        updated = True
        while updated:
            updated = False
            for dst, reachables in reachable_from.copy().items():
                before = len(reachables)
                for S in reachables.copy():
                    if dst in reachable_from[S]:
                        return True
                    reachables.update(reachable_from[S])
                if len(reachables) != before:
                    updated = True
        return False

    def compute_max_size_and_depth(self) -> tuple[int, int]:
        """
        Return max size and max depth
        """
        # Compute transitive closure
        reachable_from: dict[U, set[V]] = defaultdict(set)
        for (P, args), dst in self.rules.items():
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
        max_size_by_state: dict[U, int] = {state: 0 for state in self.states}
        max_depth_by_state: dict[U, int] = {state: 0 for state in self.states}
        for (P, args), dst in self.rules.items():
            if len(args) == 0:
                max_size_by_state[dst] = 1
                max_depth_by_state[dst] = 1
        updated = True
        while updated:
            previous_size = max_size_by_state.copy()
            previous_depth = max_depth_by_state.copy()
            for (P, args), dst in self.rules.items():
                if len(args) > 0 and all(max_size_by_state[arg] > 0 for arg in args):
                    size = sum(max_size_by_state[arg] for arg in args) + 1
                    depth = max(max_depth_by_state[arg] for arg in args) + 1
                    max_size_by_state[dst] = max(size, max_size_by_state[dst])
                    max_depth_by_state[dst] = max(depth, max_depth_by_state[dst])
            updated = (
                previous_size != max_size_by_state
                or previous_depth != max_depth_by_state
            )

        return max(max_size_by_state[f] for f in self.finals), max(
            max_depth_by_state[f] for f in self.finals
        )

    def __str__(self) -> str:
        s = "finals:" + ", ".join(sorted(map(str, self.finals))) + "\n"
        s += "letters:" + ", ".join(sorted(map(str, self.alphabet))) + "\n"
        s += "states:" + ", ".join(sorted(map(str, self.states))) + "\n"
        lines = []
        for (P, args), dst in self.rules.items():
            add = ""
            if len(args) > 0:
                add = " ".join(map(str, args))
            lines.append(f"{dst} <- '{P}' {add}")

        return s + "\n".join(sorted(lines))
