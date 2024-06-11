import importlib.util
import pathlib
import sys
import time

import pytest
from __experimental__._base import _ExperimentalLoader
from __experimental__._features import lazy_import

# FIXME: Make tests more comprehensive.


def test_finder_present_only_in_with_block():
    assert sys.meta_path[0] != lazy_import._LAZY_FINDER

    with lazy_import.lazy_module_import():
        assert sys.meta_path[0] is lazy_import._LAZY_FINDER

    # Things should go back to normal.
    assert sys.meta_path[0] != lazy_import._LAZY_FINDER


def test_finder_only_tries_removing_self():
    before_first = sys.meta_path[0]

    with lazy_import.lazy_module_import():
        assert sys.meta_path[0] is lazy_import._LAZY_FINDER
        del sys.meta_path[0]

    # Things should go back to normal.
    assert before_first is sys.meta_path[0]


def test_nonexistent_import():
    with pytest.raises(ModuleNotFoundError):
        import aaaaaaaaaaaaa  # type: ignore # Unused and also doesn't exist.

    with pytest.raises(ModuleNotFoundError):  # noqa: SIM117 # Better visual if nested.
        with lazy_import.lazy_module_import():
            import aaaaaaaaaaaaa  # type: ignore # noqa: F811 # Doesn't exist, also redefines name.

    # Things should go back to normal.
    with pytest.raises(ModuleNotFoundError):
        import aaaaaaaaaaaaa  # type: ignore # noqa: F811 # Doesn't exist, also redefines name.


def test_finder(tmp_path: pathlib.Path):
    sample_text = """\
from __future__ import annotations

from __experimental__ import lazy_import

import sys
import typing

first_finder = sys.meta_path[0]
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

    assert isinstance(module.first_finder, lazy_import._LazyFinder)
