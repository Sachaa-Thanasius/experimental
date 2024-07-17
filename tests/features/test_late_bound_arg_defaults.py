import __future__

import ast
import importlib.util
import pathlib
import types

from __experimental__._core import _ExperimentalLoader
from __experimental__._features import late_bound_arg_defaults as late_bind


# TODO: Make tests more comprehensive.


original_source = """\
from typing import Dict, List

def test_func(
    z: float,
    a: int = 1,
    b: List[int] => ([a] * a),
    /,
    c: Dict[str, int] => ({str(a): b}),
    *,
    d: str => (str(a) + str(c)),
):
    return (z, a, b, c, d)
"""

post_retokenize_source = """\
from typing import Dict, List

def test_func(
    z: float,
    a: int = 1,
    b: List[int] = _DEFER_MARKER([a] * a),
    /,
    c: Dict[str, int] = _DEFER_MARKER({str(a): b}),
    *,
    d: str = _DEFER_MARKER(str(a) + str(c)),
):
    return (z, a, b, c, d)
"""


def test_transform_source():
    retokenized_source = late_bind.transform_source(original_source)
    assert retokenized_source == post_retokenize_source


def test_transform_ast():
    globals_ns: dict[str, object] = {}

    tree = late_bind.transform_ast(ast.parse(post_retokenize_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_ns)

    test_func = globals_ns["test_func"]

    assert isinstance(test_func, types.FunctionType)
    assert isinstance(test_func.__defaults__, tuple)
    assert test_func.__defaults__[0] == 1
    assert isinstance(test_func.__defaults__[1], late_bind.DeferredExpr)
    assert isinstance(test_func.__defaults__[2], late_bind.DeferredExpr)


def test_transform_ast_with_docstring():
    original_source = f'"""Module level docstring"""\n{post_retokenize_source}'
    globals_ns: dict[str, object] = {}

    tree = late_bind.transform_ast(ast.parse(original_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_ns)

    module_doc = globals_ns["__doc__"]
    test_func = globals_ns["test_func"]

    assert module_doc == "Module level docstring"
    assert isinstance(test_func, types.FunctionType)


def test_transform_ast_with_future_import():
    original_source = f"from __future__ import annotations\n{post_retokenize_source}"

    globals_ns: dict[str, object] = {}

    tree = late_bind.transform_ast(ast.parse(original_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_ns)

    anns = globals_ns["annotations"]
    test_func = globals_ns["test_func"]

    assert anns == __future__.annotations
    assert isinstance(test_func, types.FunctionType)


def test_transform_ast_with_docstring_and_future_import():
    original_source = f'"""Module level docstring"""\nfrom __future__ import annotations\n{post_retokenize_source}'

    globals_ns: dict[str, object] = {}

    tree = late_bind.transform_ast(ast.parse(original_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_ns)

    module_doc = globals_ns["__doc__"]
    anns = globals_ns["annotations"]
    test_func = globals_ns["test_func"]

    assert module_doc == "Module level docstring"
    assert anns == __future__.annotations
    assert isinstance(test_func, types.FunctionType)


def test_loader(tmp_path: pathlib.Path):
    sample_text = """\
from typing import Dict, List

from __experimental__ import late_bound_arg_defaults

def example_func(
    z: float,
    a: int = 1,
    b: List[int] => ([a] * a),
    /,
    c: Dict[str, int] => ({str(a): b}),
    *,
    d: str => (str(z) + str(c)),
) -> str:
    return z, a, b, c, d
"""

    # Boilerplate to dynamically create and load this module.
    tmp_init = tmp_path / "__init__.py"
    tmp_init.touch()
    tmp_file = tmp_path / "sample.py"
    tmp_file.write_text(sample_text, encoding="utf-8")

    module_name = "sample"
    path = tmp_file.resolve()

    spec = importlib.util.spec_from_file_location(module_name, path, loader=_ExperimentalLoader(module_name, str(path)))

    assert spec
    assert spec.loader

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    example_func = module.example_func

    z, a, b, c, d = example_func(2.0, 3)
    assert z == 2.0
    assert a == 3
    assert b == [3, 3, 3]
    assert c == {"3": [3, 3, 3]}
    assert d == "2.0{'3': [3, 3, 3]}"
