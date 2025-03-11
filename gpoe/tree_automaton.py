from collections import defaultdict
from itertools import combinations_with_replacement, product
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
        self.finals = finals
        self.rules = rules
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

    def __remove_unproductive__(self) -> None:
        removed = True
        while removed:
            removed = False
            consumed: Set[U] = {q for q in self.finals}
            for _, args in self.rules:
                for arg in args:
                    consumed.add(arg)
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

    def read_product(self, other: "DFTA[W, V]") -> "DFTA[Tuple[U, W], V]":
        """
        Read self and other.
        """
        rules: Dict[
            Tuple[
                V,
                Tuple[Tuple[U, W], ...],
            ],
            Tuple[U, W],
        ] = {}
        # Update rules
        for (l1, args1), dst1 in self.rules.items():
            for (l2, args2), dst2 in other.rules.items():
                if len(args1) != len(args2) or l1 != l2:
                    continue
                S = (l1, tuple((a, b) for a, b in zip(args1, args2)))
                rules[S] = (dst1, dst2)
        # Update final states
        finals = set()
        for dst1 in self.finals:
            for dst2 in other.finals:
                finals.add((dst1, dst2))
        out = DFTA(rules, finals)
        return out

    def read_union(
        self,
        other: "DFTA[W, V]",
        fusion: Callable[[Optional[U], Optional[W]], X] = lambda x, y: (x, y),  # type: ignore
    ) -> "DFTA[X, V]":
        """
        Read self or other.
        """
        rules: Dict[
            Tuple[
                V,
                Tuple[X, ...],
            ],
            X,
        ] = {}
        # Update rules
        mapping_s = defaultdict(list)
        mapping_o = defaultdict(list)
        # Compute all alternatives
        finals = set()
        ostates = other.states
        for a in self.states:
            for b in ostates:
                f = fusion(a, b)
                mapping_o[b].append(f)
                mapping_s[a].append(f)
            mapping_s[a].append(fusion(a, None))
            if a in self.finals:
                finals |= set(mapping_s[a])
        for b in ostates:
            mapping_o[b].append(fusion(None, b))
            if b in other.finals:
                finals |= set(mapping_o[b])

        for (l1, args1), dst1 in self.rules.items():
            cases = [mapping_s[x] for x in args1]
            new_dst = fusion(dst1, None)
            for new_args in product(*cases):
                rules[(l1, new_args)] = new_dst

        for (l2, args2), dst2 in other.rules.items():
            cases = [mapping_o[x] for x in args2]
            new_dst = fusion(None, dst2)
            for new_args in product(*cases):
                rules[(l2, new_args)] = new_dst
        for (l1, args1), dst1 in self.rules.items():
            for (l2, args2), dst2 in other.rules.items():
                if len(args1) != len(args2) or l1 != l2:
                    continue
                S = (l1, tuple(fusion(a, b) for a, b in zip(args1, args2)))
                rules[S] = fusion(dst1, dst2)

        out = DFTA(rules, finals)
        out.reduce()
        return out

    def determinize(self) -> "DFTA[tuple[U, ...], V]":
        """

        Adapated from TATA p26.
        """
        rules = {}

        has_added = True
        states = []
        while has_added:
            has_added = False
            for (letter, args), q in self.rules.items():
                if len(args) == 0:
                    key = (letter, tuple())
                    if key in rules:
                        has_added = q in rules[key]
                        rules[key].add(q)
                    else:
                        rules[key] = {q}
                        states.append(rules[key])
                        has_added = True

                else:
                    possibles = [[s for s in states if qi in s] for qi in args]
                    if any(len(x) == 0 for x in possibles):
                        continue
                    for combination in product(*possibles):
                        key = (letter, combination)
                        if key in rules:
                            has_added = q in rules[key]
                            rules[key].add(q)
                        else:
                            rules[key] = {q}
                            states.append(rules[key])
                            has_added = True

        new_finals = set()
        for (letter, sargs), s in rules.items():
            if s not in new_finals and any(q in s for q in self.finals):
                new_finals.add(s)
            for s in sargs:
                if s not in new_finals and any(q in s for q in self.finals):
                    new_finals.add(s)

        return DFTA(
            {
                (letter, tuple(tuple(s) for s in derivation)): tuple(v)
                for (letter, derivation), v in rules.items()
            },
            {tuple(s) for s in new_finals},
        )

    def complement(self) -> "DFTA[tuple[U, ...], V]":
        det = self.determinize()
        new_finals = set()
        for state in det.states:
            if state not in det.finals:
                new_finals.add(state)
        return DFTA({k: v for k, v in det.rules.items()}, new_finals)

    @overload
    def minimise(self, mapping: Callable[[Tuple[U, ...]], W]) -> "DFTA[W, V]":
        pass

    @overload
    def minimise(self, mapping: Literal[None] = None) -> "DFTA[Tuple[U, ...], V]":
        pass

    def minimise(
        self, mapping: Union[Literal[None], Callable[[Tuple[U, ...]], W]] = None
    ) -> "Union[DFTA[Tuple[U, ...], V], DFTA[W, V]]":
        """
        Assumes this is a reduced DTFA.
        Mapping is used to map states equivalence classes to new identifiers if given like map_states.

        Adapted algorithm from:
        Brainerd, Walter S.. “The Minimalization of Tree Automata.” Inf. Control. 13 (1968): 484-491.
        """
        # 1. Build consumer_of
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
        state2cls: Dict[U, int] = {
            q: 0 if q not in self.finals else 1 for q in self.states
        }
        cls2states: Dict[int, Tuple[U, ...]] = {
            j: tuple({q for q, i in state2cls.items() if i == j}) for j in [0, 1]
        }

        n = 1
        finished = False

        # Routine
        def are_equivalent(a: U, b: U) -> bool:
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
                while cls:
                    new_cls = []
                    representative = cls.pop()
                    new_cls.append(representative)
                    next_cls = []
                    for q in cls:
                        if are_equivalent(representative, q):
                            new_cls.append(q)
                        else:
                            next_cls.append(q)
                    cls = next_cls
                    if len(cls) != 0:
                        # Create new equivalence class
                        n += 1
                        for q in new_cls:
                            state2cls[q] = n
                        cls2states[n] = tuple(new_cls)
                        finished = False
                    else:
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

    def trees_at_size(self, size: int) -> int:
        """
        Return the number of trees produced of the given size.
        """

        def __integer_partitions__(
            k: int, n: int
        ) -> Generator[Tuple[int, ...], None, None]:
            choices = list(range(1, n - k + 2))
            for elements in combinations_with_replacement(choices, k):
                if sum(elements) == n:
                    yield elements

        states = self.states
        count: dict[U, dict[int, int]] = {state: {} for state in states}
        for csize in range(1, size + 1):
            for state in states:
                count[state][csize] = 0
                for derivation in self.reversed_rules[state]:
                    _, args = derivation
                    if len(args) == 0 and csize == 1:
                        count[state][csize] += 1
                    elif len(args) > 0:
                        for partition in __integer_partitions__(len(args), csize - 1):
                            total = 1
                            for arg_size, arg in zip(partition, args):
                                total *= count[arg][arg_size]
                            count[state][csize] += total

        return sum(count[state][size] for state in self.finals)

    def __repr__(self) -> str:
        s = "finals:" + ",".join(sorted(map(str, self.finals))) + "\n"
        s += "terminals:" + ",".join(sorted(map(str, self.alphabet))) + "\n"
        s += "nonterminals:" + ",".join(sorted(map(str, self.states))) + "\n"
        lines = []
        for (P, args), dst in self.rules.items():
            add = ""
            if len(args) > 0:
                add = "," + ",".join(map(str, args))
            lines.append(f"{dst},{P}{add}")

        return s + "\n".join(sorted(lines))

    def __str__(self) -> str:
        s = "finals:" + ", ".join(sorted(map(str, self.finals))) + "\n"
        s += "terminals:" + ", ".join(sorted(map(str, self.alphabet))) + "\n"
        s += "nonterminals:" + ", ".join(sorted(map(str, self.states))) + "\n"
        lines = []
        for (P, args), dst in self.rules.items():
            add = ""
            if len(args) > 0:
                add = " ".join(map(str, args))
            lines.append(f"{dst} <- '{P}' {add}")

        return s + "\n".join(sorted(lines))
