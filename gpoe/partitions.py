from typing import Generator, Tuple


def integer_partitions(k: int, n: int) -> Generator[Tuple[int, ...], None, None]:
    if k > n: return
    tup = [n - k + 1] + [1] * (k - 1)
    yield tuple(tup)
    while True:
        if tup[-1] == n - k + 1: break
        carry = tup[-1] - 1
        tup[-1] = 1
        for i in range(k - 2, -1, -1):
            if tup[i] > 1: break
        tup[i] -= 1
        tup[i + 1] += 1 + carry
        yield tuple(tup)