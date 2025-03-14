from itertools import combinations_with_replacement, permutations
from typing import Generator, Tuple


def integer_partitions(k: int, n: int) -> Generator[Tuple[int, ...], None, None]:
    choices = list(range(1, n - k + 2))
    permut = permutations(range(k))
    for elements in combinations_with_replacement(choices, k):
        if sum(elements) == n:
            done = set()
            for p in permut:
                new = tuple(elements[i] for i in p)
                if new not in done:
                    yield new
                    done.add(new)
