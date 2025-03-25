from itertools import product


def return_type(type_req: str) -> str:
    return type_req.split("->")[-1].strip()


def arguments(type_req: str) -> tuple[str, ...]:
    return tuple(map(lambda x: x.strip(), type_req.split("->")[:-1]))


def parse(type_req: str) -> tuple[tuple[str, ...], str]:
    elems = tuple(map(lambda x: x.strip(), type_req.split("->")))
    return elems[:-1], elems[-1]


def all_variants(type_req: str) -> list[str]:
    elements = map(lambda x: x.strip(), type_req.split("->"))
    names = []
    names2possibles = {}
    for i, el in enumerate(elements):
        if el.startswith("'"):
            # Polymorphic type
            if "[" in el and "]" in el:
                sum_parenthesis = el[el.find("[") + 1 : -1]
                possibles = all_variants(sum_parenthesis)
                name = el[1 : el.find("[")].strip()
                names2possibles[name] = possibles
            else:
                name = el[1:]
                assert name in names2possibles, (
                    f"polymorphic name '{name}' used before definition! defined: {', '.join(map(str, names2possibles.keys()))}"
                )
            names.append(name)
        elif "|" in el:
            # Sum type
            names.append(i)
            possibles = list(map(lambda x: x.strip(), el.split("|")))
            names2possibles[i] = possibles
        else:
            names.append(i)
            names2possibles[i] = [el]
    out = []
    possibles = [[(name, x) for x in poss] for name, poss in names2possibles.items()]

    def get_by_name(n, conf):
        return [t for name, t in conf if name == n][0]

    for conf in product(*possibles):
        type_req_variant = "->".join(map(lambda n: get_by_name(n, conf), names))
        out.append(type_req_variant)
    return out
