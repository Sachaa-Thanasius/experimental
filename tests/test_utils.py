import ast

import pytest
from __experimental__._utils.ast_helpers import collapse_plain_attribute_or_name, compare_asts
from __experimental__._utils.token_helpers import get_imported_experimental_flags

empty_set: set[str] = set()


@pytest.mark.parametrize(
    ("test_source", "expected_result"),
    [
        pytest.param("", empty_set, id="trivial"),
        pytest.param(
            "from __experimental__ import inline_import\n",
            {"inline_import"},
            id="only import",
        ),
        pytest.param(
            "from __future__ import annotations\nfrom __experimental__ import inline_import\n",
            {"inline_import"},
            id="experimental after future import",
        ),
        pytest.param(
            "'''module docstring'''\n\nfrom __experimental__ import inline_import\n",
            {"inline_import"},
            id="module docstring before",
        ),
        pytest.param(
            "'''module docstring'''\n"
            "\n"
            "from __experimental__ import inline_import # comment here\n"
            "# Another comment here\n",
            {"inline_import"},
            id="with inline comments",
        ),
        pytest.param(
            "from __future__ import annotations\n"
            "\n"
            "from a import thing\n"
            "from b import thing\n"
            "\n"
            "from __experimental__ import late_bound_arg_defaults\n",
            {"late_bound_arg_defaults"},
            id="after multiple imports",
        ),
        pytest.param(
            "from __experimental__ import late_bound_arg_defaults, inline_import\n",
            {"inline_import", "late_bound_arg_defaults"},
            id="with multiple features",
        ),
        pytest.param(
            "from __experimental__ import (\n"
            "   late_bound_arg_defaults,  # comment 1\n"
            "   inline_import,  # comment 2\n"
            ")\n",
            {"inline_import", "late_bound_arg_defaults"},
            id="with multiple features parenthesized and comments",
        ),
        pytest.param(
            "import a\n\ndef hello_world() -> None: pass\n\nfrom __experimental__ import inline_import",
            empty_set,
            id="stops at first function",
        ),
        pytest.param(
            "import a\n\nclass Hello: pass\n\nfrom __experimental__ import inline_import",
            empty_set,
            id="stops at first class",
        ),
    ],
)
def test_get_imported_experimental_flags(test_source: str, expected_result: set[str]):
    result = get_imported_experimental_flags(test_source)
    assert result == expected_result


@pytest.mark.parametrize(
    ("test_source", "expected_result"),
    [
        ("a", "a"),
        ("a.b.c", "a.b.c"),
        ("a.b.c.d.e.f", "a.b.c.d.e.f"),
    ],
)
def test_collapse_plain_attribute_or_name(test_source: str, expected_result: str):
    tree = ast.parse(test_source)
    node = tree.body[0].value
    assert collapse_plain_attribute_or_name(node) == expected_result


@pytest.mark.parametrize(
    "test_source",
    [
        "a[0]",
        "a.b.c[0]",
        "a.b.c.d[1].e.f",
        "a.b.c.d().e.f",
    ],
)
def test_collapse_plain_attribute_or_name_bad_input(test_source: str):
    tree = ast.parse(test_source)
    node = tree.body[0].value
    with pytest.raises(TypeError):
        collapse_plain_attribute_or_name(node)


@pytest.mark.parametrize(
    ("test_source", "expected_result"),
    [
        ("a = func(a)", True),
        ("a[0] = func(a[0])", True),
        ("a.b.c = func(a.b.c)", True),
        ("a.b = func(a)", False),
        ("a = func(a.b)", False),
        ("hello().a = func(a)", False),
    ],
)
def test_compare_ast(test_source: str, expected_result: bool):
    tree = ast.parse(test_source)
    left_side = tree.body[0].targets[0]
    first_arg = tree.body[0].value.args[0]
    assert compare_asts(left_side, first_arg) == expected_result
