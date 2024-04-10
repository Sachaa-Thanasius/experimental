import importlib.util
import sys
import time

import pytest
from __experimental__ import _lazy_import as lazy_import

# FIXME: Make tests more comprehensive.


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


def test_regular_import():
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


def test_recipe_docs():
    start_time = time.perf_counter()

    lazy_concurrent_futures = lazy_import_docs("concurrent.futures")
    lazy_contextlib = lazy_import_docs("contextlib")
    lazy_inspect = lazy_import_docs("inspect")
    lazy_itertools = lazy_import_docs("itertools")
    lazy_types = lazy_import_docs("types")
    lazy_importlib_abc = lazy_import_docs("importlib.abc")

    total_time = time.perf_counter() - start_time

    assert lazy_concurrent_futures.as_completed
    assert lazy_contextlib.contextmanager
    assert lazy_inspect.getsource
    assert lazy_itertools.chain
    assert lazy_types.ModuleType
    assert lazy_importlib_abc.MetaPathFinder

    print(f"Time taken for lazy import (based on importlib recipe) = {total_time}")


def test_lazy_module_import():
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
