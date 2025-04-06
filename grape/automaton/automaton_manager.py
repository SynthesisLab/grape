from enum import StrEnum

from grape.automaton.tree_automaton import DFTA


class AutomatonFormat(StrEnum):
    EBNF = ".ebnf"
    GRAPE = ".grape"

    @staticmethod
    def from_str(content: str) -> "AutomatonFormat":
        for val, enum in AutomatonFormat._value2member_map_.items():
            if val == content:
                return enum
        raise ValueError(f"invalid automaton format: '{content}")


def dump_automaton_to_file(dfta: DFTA, file: str) -> None:
    extension = file[file.rfind(".") :]
    with open(file, "w") as fd:
        fd.write(dump_automaton_to_str(dfta, AutomatonFormat.from_str(extension)))


def dump_automaton_to_str(dfta: DFTA, format: AutomatonFormat) -> str:
    if format == AutomatonFormat.GRAPE:
        s = "finals:" + ",".join(sorted(map(str, dfta.finals))) + "\n"
        s += "letters:" + ",".join(sorted(map(str, dfta.alphabet))) + "\n"
        s += "states:" + ",".join(sorted(map(str, dfta.states))) + "\n"
        lines = []
        for (P, args), dst in dfta.rules.items():
            add = ""
            if len(args) > 0:
                add = "," + ",".join(map(str, args))
            lines.append(f"{dst},{P}{add}")

        return s + "\n".join(sorted(lines))
    elif format == AutomatonFormat.EBNF:
        elements = []
        dfta = dfta.map_states(lambda x: str(x).replace("=", "_").replace("-", "_"))
        dfta.refresh_reversed_rules()
        for dst, derivations in dfta.reversed_rules.items():
            s = f"{dst} = "
            s_elements = []
            for P, args in derivations:
                end = ", ".join(map(str, args))
                if len(args):
                    end = " , " + end
                s_elements.append(f'"{P}"{end}')
            elements.append(s + " | ".join(s_elements) + ";")
        return "\n".join(elements)

    else:
        raise ValueError(f"unsupported format:{format}")


def load_automaton_from_file(file: str) -> DFTA[str, str]:
    extension = file[file.rfind(".") :]
    with open(file) as fd:
        content = fd.read()
        return load_automaton_from_str(content, AutomatonFormat.from_str(extension))


def load_automaton_from_str(data: str, format: AutomatonFormat) -> DFTA[str, str]:
    if format == AutomatonFormat.GRAPE:
        lines = data.splitlines()
        finals = set(
            map(lambda x: x.strip(), lines.pop(0)[len("finals:") :].split(","))
        )
        letters = set(
            map(lambda x: x.strip(), lines.pop(0)[len("letters:") :].split(","))
        )
        states = set(
            map(lambda x: x.strip(), lines.pop(0)[len("states:") :].split(","))
        )
        rules = {}
        for line_no, line in enumerate(lines):
            elements = line.split(",")
            dst = elements.pop(0)
            assert dst in states, (
                f"loading at line{3 + line_no}: state: '{dst}' not declared beforehand!"
            )
            letter = elements.pop(0)
            assert letter in letters, (
                f"loading at line{3 + line_no}: letter: '{letter}' not declared beforehand!"
            )
            args = tuple(elements)
            for arg in args:
                assert arg in states, (
                    f"loading at line{3 + line_no}: state: '{arg}' not declared beforehand!"
                )
            rules[(letter, args)] = dst
        return DFTA(rules, set(finals))
    elif format == AutomatonFormat.EBNF:
        data = data.replace("\n", " ")
        terminal_chars = ['"', "'"]
        elements = data.split(";")
        rules = {}
        finals = set()
        for element in elements:
            rules_for_nonterminals = [
                x.strip() for x in element.split("=") if len(x.strip()) > 0
            ]
            if len(rules_for_nonterminals) <= 1:
                continue
            dst = rules_for_nonterminals.pop(0).strip()
            finals.add(dst)
            for sub_rule in "=".join(rules_for_nonterminals).split("|"):
                sub_elements = [
                    x.strip() for x in sub_rule.split(",") if len(x.strip()) > 0
                ]
                terminal = sub_elements.pop(0).strip()
                assert any(
                    terminal.startswith(c) and terminal.endswith(c)
                    for c in terminal_chars
                ), (
                    f"error parsing rule: {element}\n\twhile handling:{sub_rule}\n\t\t<<{terminal}>> could not be parsed as a terminal"
                )
                args = tuple(map(lambda x: x.strip(), sub_elements))
                rules[(terminal[1:-1], args)] = dst
        return DFTA(rules, finals)

    else:
        raise ValueError(f"unsupported format:{format}")
