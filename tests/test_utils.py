from typing import Set

import pytest
from __experimental__._utils.token_helper import get_imported_experimental_flags


@pytest.mark.parametrize(
    "test_source, expected_result",
    [
        pytest.param("", set(), id="trivial"),
        pytest.param(
            "from __experimental__ import inline_import\n",
            {"inline_import"},
            id="only import",
        ),
        pytest.param(
            "from __future__ import annotations\n"
            "from __experimental__ import inline_import\n",
            {"inline_import"},
            id="experimental after future import"
        ),
        pytest.param(
            "'''module docstring'''\n"
            "\n"
            "from __experimental__ import inline_import\n",
            {"inline_import"},
            id="module docstring before"
        ),
        pytest.param(
            "'''module docstring'''\n"
            "\n"
            "from __experimental__ import inline_import # comment here\n"
            "# Another comment here\n",
            {"inline_import"},
            id="with inline comments"
        ),
        pytest.param(
            "from __future__ import annotations\n"
            "\n"
            "from a import thing\n"
            "from b import thing\n"
            "\n"
            "from __experimental__ import late_bound_arg_defaults\n",
            {"late_bound_arg_defaults"},
            id="after multiple imports"
        ),
        pytest.param(
            "from __experimental__ import late_bound_arg_defaults, inline_import\n",
            {"inline_import", "late_bound_arg_defaults"},
            id="with multiple features"
        ),
        pytest.param(
            "from __experimental__ import (\n"
            "   late_bound_arg_defaults,  # comment 1\n"
            "   inline_import,  # comment 2\n"
            ")\n",
            {"inline_import", "late_bound_arg_defaults"},
            id="with multiple features parenthesized and comments"
        ),
        pytest.param(
            "import a\n"
            "\n"
            "def hello_world() -> None: pass\n"
            "\n"
            "from __experimental__ import inline_import",
            set(),
            id="stops at first function"
        ),
        pytest.param(
            "import a\n"
            "\n"
            "class Hello: pass\n"
            "\n"
            "from __experimental__ import inline_import",
            set(),
            id="stops at first class"
        ),
        
    ],
)
def test_get_imported_experimental_flags(test_source: str, expected_result: Set[str]) -> None:
    result = get_imported_experimental_flags(test_source)
    assert result == expected_result, f"{result=}, {expected_result}"
