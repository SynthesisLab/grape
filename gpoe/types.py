def return_type(type_req: str) -> str:
    return type_req.split("->")[-1].strip()


def arguments(type_req: str) -> tuple[str, ...]:
    return tuple(map(lambda x: x.strip(), type_req.split("->")[:-1]))


def parse(type_req: str) -> tuple[tuple[str, ...], str]:
    elems = tuple(map(lambda x: x.strip(), type_req.split("->")))
    return elems[:-1], elems[-1]
