import ast
import tokenize
from io import StringIO

import pytest
from __experimental__ import _inline_import as inline_import, install


@pytest.mark.parametrize(
    "test_source, expected_result",
    [
        ("mod1!.attr1('abcd')", "_IMPORTLIB_MARKER(mod1).attr1('abcd')"),
        ("mod1.mod2!.attr3('abcd')", "_IMPORTLIB_MARKER(mod1.mod2).attr3('abcd')"),
    ],
)
def test_modify_source(test_source: str, expected_result: str) -> None:
    retokenized_source = inline_import.transform_source(test_source)
    assert retokenized_source == expected_result


@pytest.mark.parametrize(
    "test_source, expected_result",
    [
        (
            "_IMPORTLIB_MARKER(mod1).attr1('abcd')",
            "import importlib\nimportlib.import_module('mod1').attr1('abcd')",
        ),
        (
            "_IMPORTLIB_MARKER(mod1.mod2).attr3('abcd')",
            "import importlib\nimportlib.import_module('mod1.mod2').attr3('abcd')",
        ),
    ],
)
def test_modify_ast(test_source: str, expected_result: str) -> None:
    transformed_source = ast.unparse(inline_import.transform_ast(ast.parse(test_source)))
    assert transformed_source == expected_result


@pytest.mark.parametrize(
    "test_source, expected_result",
    [
        (
            "mod1!.attr1('abcd')",
            "import importlib\nimportlib.import_module('mod1').attr1('abcd')",
        ),
        (
            "mod1.mod2!.attr3('abcd')",
            "import importlib\nimportlib.import_module('mod1.mod2').attr3('abcd')",
        ),
    ],
)
def test_parse(test_source, expected_result) -> None:
    assert ast.unparse(inline_import.parse(test_source)) == expected_result
