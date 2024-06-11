"""Benchmark script for various lazy loading mechanisms."""

import importlib.util
import sys
import time
from collections.abc import Callable

from __experimental__._features import lazy_import


def lazy_import_recipe(name: str):
    """Lazy import recipe from the importlib docs.

    Source: https://docs.python.org/3.11/library/importlib.html#implementing-lazy-imports
    """

    spec = importlib.util.find_spec(name)
    # Let None in any of the below cause an exception.
    loader = importlib.util.LazyLoader(spec.loader)  # pyright: ignore [reportArgumentType, reportOptionalMemberAccess]
    spec.loader = loader  # pyright: ignore [reportOptionalMemberAccess]
    module = importlib.util.module_from_spec(spec)  # pyright: ignore [reportArgumentType]
    sys.modules[name] = module
    loader.exec_module(module)
    return module


def run_regular_import(module_name: str) -> None:
    importlib.import_module(module_name)


def run_lazy_recipe_import(module_name: str) -> None:
    lazy_import_recipe(module_name)


def run_my_lazy_import(module_name: str) -> None:
    with lazy_import.lazy_module_import():
        importlib.import_module(module_name)


def run_benchmark(repetitions: int, module_names: tuple[str, ...], bench_func: Callable[[str], object]) -> float:
    start_time = time.perf_counter()

    for _ in range(repetitions):
        for mod_name in module_names:
            bench_func(mod_name)

        for mod_name in module_names:
            del sys.modules[mod_name]

    end_time = time.perf_counter()
    return end_time - start_time


def main(repetitions: int) -> None:
    # Create the test cases.
    module_names = ("concurrent.futures", "contextlib", "inspect", "itertools", "types", "importlib.abc")

    # fmt: off
    bench_functions = (
        ("regular",                 run_regular_import),
        ("lazy importlib recipe",   run_lazy_recipe_import),
        ("custom lazy",             run_my_lazy_import),
    )
    # fmt: on

    # Run the tests and collect the results.
    results = {name: run_benchmark(repetitions, module_names, bench_func) for name, bench_func in bench_functions}
    sorted_results = sorted(results.items(), key=lambda r: r[1])

    # Pretty-print the results.
    PADDING = 30

    print(f"{f'{repetitions} Repetitions of {len(module_names)} Imports':>{PADDING}} │ Time (s)")
    print(f"{'─' * PADDING}─┼──────────")
    print("\n".join(f"{name:>{PADDING}} │ {timespan:.5f}" for name, timespan in sorted_results))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--repeat", default=100, type=int, required=False)
    args = parser.parse_args()
    raise SystemExit(main(args.repeat))
