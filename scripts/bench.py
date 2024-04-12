"""A small script for timing the late bound arg defaults against the current sentinel idiom."""

import ctypes
import sys
from itertools import takewhile
from typing import Callable, List, Optional, Tuple

from __experimental__._features.late_bound_arg_defaults import _defer, _evaluate_late_binding

# ====== Everything below this comment is the desugared version of this:

# def example_called(
#     a: int,
#     b: float = 1.0,
#     /,
#     ex: str = "hello",
#     *,
#     c: List[object] => (["Preceding args", a, b, ex]),
#     d: bool = False,
#     e: int => (len(c)),
# ) -> Tuple[List[object], int]:
#     _evaluate_late_binding(locals())
#     return c, e


def example_called(
    a: int,
    b: float = 1.0,
    /,
    ex: str = "hello",
    *,
    c: List[object] = _defer(lambda a, b, ex: ["Preceding args", a, b, ex]),  # type: ignore # noqa: B008
    d: bool = False,
    e: int = _defer(lambda a, b, ex, c, d: len(c)),  # type: ignore
) -> Tuple[List[object], int]:
    _evaluate_late_binding(locals())
    return c, e


def example_inlined(
    a: int,
    b: float = 1.0,
    /,
    ex: str = "hello",
    *,
    c: List[object] = _defer(lambda a, b, ex: ["Preceding args", a, b, ex]),  # type: ignore # noqa: B008
    d: bool = False,
    e: int = _defer(lambda a, b, ex, c, d: len(c)),  # type: ignore
) -> Tuple[List[object], int]:
    new_locals = locals().copy()
    for arg_name, arg_val in new_locals.items():
        if isinstance(arg_val, _defer):
            new_locals[arg_name] = arg_val(*takewhile(lambda val: not isinstance(val, _defer), new_locals.values()))

    frame = sys._getframe()
    try:
        frame.f_locals.update(new_locals)
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))
    finally:
        del frame

    del new_locals
    try:
        del arg_name  # type: ignore
    except UnboundLocalError:
        pass
    try:
        del arg_val  # type: ignore
    except UnboundLocalError:
        pass

    return c, e


def example_none_idiom(
    a: int,
    b: float = 1.0,
    /,
    ex: str = "hello",
    *,
    c: Optional[List[object]] = None,
    d: bool = False,
    e: Optional[int] = None,
) -> Tuple[List[object], int]:
    if c is None:
        c = ["Preceding args", a, b, ex]
    if e is None:
        e = len(c)
    return c, e


# ====== The functions that do the "benchmarking".


def run_timer(iterations: int) -> None:
    import timeit
    from functools import partial

    expected_result = (["Preceding args", 1, 1.0, "hello"], 4)

    for text, callback in zip(
        (f"With call:{' ' * 15}", f"With inlining:{' ' * 11}", "With None sentinel idiom:"),
        (example_called, example_inlined, example_none_idiom),
    ):
        test_callback = partial(callback, 1)
        assert test_callback() == expected_result
        print(text, timeit.timeit(test_callback, number=iterations))


def profile_func(callback: Callable[..., object], iterations: int):
    for _ in range(iterations):
        callback(1)


def run_profiler(iterations: int):
    import cProfile

    for callback in ("example_called", "example_inlined", "example_none_idiom"):
        cProfile.run(f"profile_func({callback}, {iterations})")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark the late_bound_arg_defaults part of __experimental__.",
    )
    parser.add_argument("-b", "--benchmark", action="store_true")
    parser.add_argument("-p", "--profile", action="store_true")
    parser.add_argument("-i", "--iterations", default=750_000, type=int)

    args = parser.parse_args()

    iterations = args.iterations
    if not (args.benchmark or args.profile):
        msg = "Pick an option to run this with, either -b or -p."
        raise RuntimeError(msg)
    if args.benchmark:
        run_timer(iterations)
    if args.profile:
        run_profiler(iterations)


if __name__ == "__main__":
    raise SystemExit(main())
