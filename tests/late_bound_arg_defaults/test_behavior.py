import ast

from __experimental__ import install, uninstall
from __experimental__.features import _late_bound_arg_defaults as late_bind

ORIGINAL_FUNC = """\
def test_func(
    z: float,
    a: int = 1,
    b: list[int] => ([a] * a),
    /,
    c: dict[str, int] => ({str(a): b}),
    *,
    d: str => (str(a) + str(c)),
) -> str:
    result = [*b, a]
    return str(result)
"""

POST_RETOKENIZE_FUNC = """\
def test_func(
    z: float,
    a: int = 1,
    b: list[int] = _PEP671_MARKER([a] * a),
    /,
    c: dict[str, int] = _PEP671_MARKER({str(a): b}),
    *,
    d: str = _PEP671_MARKER(str(a) + str(c)),
) -> str:
    result = [*b, a]
    return str(result)
"""

POST_AST_TRANSFORM_FUNC = """\
from __experimental__.features._late_bound_arg_defaults import _defer, _evaluate_late_binding

def test_func(z: float, a: int=1, b: list[int]=_defer(lambda z, a: [a] * a), /, c: dict[str, int]=_defer(lambda z, a, b: {str(a): b}), *, d: str=_defer(lambda z, a, b, c: str(a) + str(c))) -> str:
    _evaluate_late_binding(locals())
    result = [*b, a]
    return str(result)\
"""


def test_func_with_late_bindings() -> None:
    def actual_late_binding_implementation_example(
        a: int,
        b: float = 1.0,
        /,
        ex: str = "hello",
        *,
        c: list[object] = late_bind._defer(lambda a, b, ex: ["Preceding args", a, b, ex]),  # noqa: B008
        d: bool = False,
        e: int = late_bind._defer(lambda a, b, ex, c, d: len(c)),
    ) -> tuple[list[object], int]:
        late_bind._evaluate_late_binding(locals())
        return c, e

    c, e = actual_late_binding_implementation_example(10)
    assert c == ["Preceding args", 10, 1.0, "hello"]
    assert e == 4


def test_modify_source() -> None:
    retokenized_source = late_bind.transform_source(ORIGINAL_FUNC)
    assert retokenized_source == POST_RETOKENIZE_FUNC


def test_modify_ast() -> None:
    transformed_source = ast.unparse(late_bind.transform_ast(ast.parse(POST_RETOKENIZE_FUNC)))
    assert transformed_source == POST_AST_TRANSFORM_FUNC


def test_modify_ast_with_docstring() -> None:
    original_source = f'"""Module level docstring"""\n{POST_RETOKENIZE_FUNC}'
    expected_result = f'"""Module level docstring"""\n{POST_AST_TRANSFORM_FUNC}'

    transformed_source = ast.unparse(late_bind.transform_ast(ast.parse(original_source)))
    assert transformed_source == expected_result


def test_modify_ast_with_future_import() -> None:
    original_source = f"from __future__ import annotations\n{POST_RETOKENIZE_FUNC}"
    expected_result = f"from __future__ import annotations\n{POST_AST_TRANSFORM_FUNC}"

    transformed_source = ast.unparse(late_bind.transform_ast(ast.parse(original_source)))
    assert transformed_source == expected_result


def test_modify_ast_with_docstring_and_future_import() -> None:
    original_source = f'"""Module level docstring"""\nfrom __future__ import annotations\n{POST_RETOKENIZE_FUNC}'
    expected_result = f'"""Module level docstring"""\nfrom __future__ import annotations\n{POST_AST_TRANSFORM_FUNC}'

    transformed_source = ast.unparse(late_bind.transform_ast(ast.parse(original_source)))
    assert transformed_source == expected_result


def test_loader() -> None:
    install()
    from tests.late_bound_arg_defaults.sample import example_func

    z, a, b, c, d = example_func(2.0, 3)
    assert z == 2.0
    assert a == 3
    assert b == [3, 3, 3]
    assert c == {"3": [3, 3, 3]}
    assert d == "2.0{'3': [3, 3, 3]}"

    uninstall()
