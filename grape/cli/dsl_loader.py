import importlib

from grape.dsl import DSL

import importlib.util
import sys
import string
import secrets


def gensym(length=32, prefix="gendsl_modulename_"):
    """
    generates a fairly unique symbol, used to make a module name,
    used as a helper function for load_module

    :return: generated symbol
    """
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    symbol = "".join([secrets.choice(alphabet) for i in range(length)])
    return prefix + symbol


def load_module(source, module_name=None):
    """
    reads file source and loads it as a module

    :param source: file to load
    :param module_name: name of module to register in sys.modules
    :return: loaded module
    """

    if module_name is None:
        module_name = gensym()

    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def __make_error_lambda(text: str) -> callable:
    def f():
        raise ValueError(text)

    return f


def load_python_file(
    file_path: str,
) -> tuple[
    DSL,
    str | None,
    dict[str, callable],
    dict[str, callable],
    set,
]:
    module = load_module(file_path)
    elements = [
        ("dsl", __make_error_lambda("No DSL specified")),
        ("target_type", lambda: "None"),
        ("sample_dict", __make_error_lambda("No Sample Dict specified")),
        ("equal_dict", dict),
        ("skip_exceptions", set),
    ]
    out = []
    for attr_name, default in elements:
        if hasattr(module, attr_name):
            out.append(getattr(module, attr_name))
        else:
            out.append(default())
    # Convert some
    out[0] = DSL(out[0])
    return tuple(out)
