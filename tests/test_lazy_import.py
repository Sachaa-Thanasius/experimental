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
        import aaaaa

    with pytest.raises(ModuleNotFoundError):  # noqa: SIM117
        with lazy_import.lazy_module_import():
            import aaaaa  # noqa: F811

    # Things should go back to normal.
    with pytest.raises(ModuleNotFoundError):
        import aaaaa  # noqa: F811


def test_finder(tmp_path: pathlib.Path) -> None:
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

    spec = importlib.util.spec_from_file_location(module_name, path)
    spec.loader = _ExperimentalLoader(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    assert isinstance(module.first_finder, lazy_import._LazyFinder)


class TestTimeDifferentImportMechanisms:
    # These have to be run individually, but the class grouping visually separates them from the rest of the tests.

    @staticmethod
    def lazy_import_docs(name: str):
        """Lazy import recipe from the importlib docs.

        Source: https://docs.python.org/3.11/library/importlib.html#implementing-lazy-imports
        """

        spec = importlib.util.find_spec(name)
        loader = importlib.util.LazyLoader(spec.loader)  # type: ignore # Let None cause an exception.
        spec.loader = loader  # type: ignore # Let None cause an exception.
        module = importlib.util.module_from_spec(spec)  # type: ignore # Let None cause an exception.
        sys.modules[name] = module
        loader.exec_module(module)
        return module

    def test_regular_import(self):
        start_time = time.perf_counter()

        import concurrent.futures
        import contextlib
        import inspect
        import itertools
        import types
        from importlib import abc

        total_time = time.perf_counter() - start_time

        assert concurrent.futures.as_completed
        assert contextlib.contextmanager
        assert inspect.getsource
        assert itertools.chain
        assert types.ModuleType
        assert abc.MetaPathFinder

        print(f"Time taken for regular import = {total_time}")

    def test_lazy_recipe_docs(self):
        start_time = time.perf_counter()

        lazy_concurrent_futures = self.lazy_import_docs("concurrent.futures")
        lazy_contextlib = self.lazy_import_docs("contextlib")
        lazy_inspect = self.lazy_import_docs("inspect")
        lazy_itertools = self.lazy_import_docs("itertools")
        lazy_types = self.lazy_import_docs("types")
        lazy_importlib_abc = self.lazy_import_docs("importlib.abc")

        total_time = time.perf_counter() - start_time

        assert lazy_concurrent_futures.as_completed
        assert lazy_contextlib.contextmanager
        assert lazy_inspect.getsource
        assert lazy_itertools.chain
        assert lazy_types.ModuleType
        assert lazy_importlib_abc.MetaPathFinder

        print(f"Time taken for lazy import (based on importlib recipe) = {total_time}")

    def test_lazy_module_import(self):
        start_time = time.perf_counter()

        with lazy_import.lazy_module_import():
            import concurrent.futures
            import contextlib
            import inspect
            import itertools
            import types
            from importlib import abc

        total_time = time.perf_counter() - start_time

        assert concurrent.futures.as_completed
        assert contextlib.contextmanager
        assert inspect.getsource
        assert itertools.chain
        assert types.ModuleType
        assert abc.MetaPathFinder

        print(f"Time taken for lazy import = {total_time}")
