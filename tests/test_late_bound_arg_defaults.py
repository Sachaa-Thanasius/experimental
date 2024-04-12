import __future__

import ast
import importlib
import importlib.util
import pathlib
import sys
import types
from typing import Any, Dict, List, Tuple

from __experimental__._base import _ExperimentalLoader
from __experimental__._features import late_bound_arg_defaults as late_bind

# FIXME: Make tests more comprehensive.


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


def test_late_binding_logic() -> None:
    def late_binding_logic_example(
        a: int,
        b: float = 1.0,
        /,
        ex: str = "hello",
        *,
        c: List[object] = late_bind._defer(lambda a, b, ex: ["Preceding args", a, b, ex]),  # noqa: B008
        d: bool = False,
        e: int = late_bind._defer(lambda a, b, ex, c, d: len(c)),
    ) -> Tuple[List[object], int]:
        late_bind._evaluate_late_binding(locals())
        return c, e

    c, e = late_binding_logic_example(10)
    assert c == ["Preceding args", 10, 1.0, "hello"]
    assert e == 4


def test_transform_source() -> None:
    retokenized_source = late_bind.transform_source(original_source)
    assert retokenized_source == post_retokenize_source


def test_transform_ast() -> None:
    globals_: Dict[str, Any] = {}

    tree = late_bind.transform_ast(ast.parse(post_retokenize_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_)

    test_func = globals_["test_func"]

    assert test_func.__defaults__[0] == 1
    assert isinstance(test_func.__defaults__[1], late_bind._defer)
    assert isinstance(test_func.__defaults__[2], late_bind._defer)


def test_transform_ast_with_docstring() -> None:
    original_source = f'"""Module level docstring"""\n{post_retokenize_source}'
    globals_: Dict[str, Any] = {}

    tree = late_bind.transform_ast(ast.parse(original_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_)

    module_doc = globals_["__doc__"]
    test_func = globals_["test_func"]

    assert module_doc == "Module level docstring"
    assert isinstance(test_func, types.FunctionType)


def test_transform_ast_with_future_import() -> None:
    original_source = f"from __future__ import annotations\n{post_retokenize_source}"

    globals_: Dict[str, Any] = {}

    tree = late_bind.transform_ast(ast.parse(original_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_)

    anns = globals_["annotations"]
    test_func = globals_["test_func"]

    assert anns == __future__.annotations
    assert isinstance(test_func, types.FunctionType)


def test_transform_ast_with_docstring_and_future_import() -> None:
    original_source = f'"""Module level docstring"""\nfrom __future__ import annotations\n{post_retokenize_source}'

    globals_: Dict[str, Any] = {}

    tree = late_bind.transform_ast(ast.parse(original_source))
    code = compile(tree, "<string>", "exec")
    exec(code, globals_)

    module_doc = globals_["__doc__"]
    anns = globals_["annotations"]
    test_func = globals_["test_func"]

    assert module_doc == "Module level docstring"
    assert anns == __future__.annotations
    assert isinstance(test_func, types.FunctionType)


def test_loader(tmp_path: pathlib.Path) -> None:
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
    tmp_init = tmp_path / "__init__.py"
    tmp_init.touch()
    tmp_file = tmp_path / "sample.py"
    tmp_file.write_text(sample_text, encoding="utf-8")

    module_name = "sample"
    path = tmp_file.resolve()

    spec = importlib.util.spec_from_file_location(module_name, path, loader=_ExperimentalLoader(module_name, str(path)))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    example_func = module.example_func

    z, a, b, c, d = example_func(2.0, 3)
    assert z == 2.0
    assert a == 3
    assert b == [3, 3, 3]
    assert c == {"3": [3, 3, 3]}
    assert d == "2.0{'3': [3, 3, 3]}"
