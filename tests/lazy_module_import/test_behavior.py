import importlib.util
import sys
import time
import types

from __experimental__ import lazy_module_import

# TODO: Make tests more comprehensive.


class catchtime:
    """Utility for timing code execution."""

    def __enter__(self):
        self.total_time = time.perf_counter()
        return self

    def __exit__(self, *_: object) -> None:
        self.total_time = time.perf_counter() - self.total_time


def lazy_import_docs(name: str) -> types.ModuleType:
    """Lazy import recipe from the importlib docs.

    Source: https://docs.python.org/3.11/library/importlib.html#implementing-lazy-imports
    """

    spec = importlib.util.find_spec(name)
    # Let presence of None cause an exception.
    loader = importlib.util.LazyLoader(spec.loader)  # type: ignore
    spec.loader = loader  # type: ignore
    module = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def test_regular_import():
    with catchtime() as ct:
        import concurrent.futures
        import contextlib
        import inspect
        import itertools
        import types
        import typing
        from importlib import abc

    assert concurrent.futures.as_completed
    print(f"Time taken for regular import = {ct.total_time}")


def test_recipe_docs():
    with catchtime() as ct:
        lazy_concurrent_futures = lazy_import_docs("concurrent.futures")
        lazy_contextlib = lazy_import_docs("contextlib")
        lazy_inspect = lazy_import_docs("inspect")
        lazy_itertools = lazy_import_docs("itertools")
        lazy_types = lazy_import_docs("types")
        lazy_typing = lazy_import_docs("typing")
        lazy_importlib_abc = lazy_import_docs("importlib.abc")

    assert lazy_concurrent_futures.as_completed
    print(f"Time taken for lazy import (based on importlib recipe) = {ct.total_time}")


def test_lazy_imp():
    with catchtime() as ct:  # noqa: SIM117 # Display the separate block.
        with lazy_module_import:
            import concurrent.futures
            import contextlib
            import inspect
            import itertools
            import types
            import typing
            from importlib import abc

    assert concurrent.futures.as_completed
    print(f"Time taken for lazy import = {ct.total_time}")


def test_delayed_circular_import():
    import typing

    from tests.lazy_module_import.sample_pkg import module1, module2

    assert typing.get_type_hints(module1.Class1.__init__) == {"scr": module2.Class2 | None}
    assert typing.get_type_hints(module2.Class2.__init__) == {"scr": module1.Class1 | None}

    import inspect

    assert inspect.get_annotations(module1.Class1.__init__, eval_str=True) == {"scr": module2.Class2 | None}
    assert inspect.get_annotations(module2.Class2.__init__, eval_str=True) == {"scr": module1.Class1 | None}
