"""A small script for timing the late bound arg defaults against the normal sentinel idiom."""

from typing import Callable, List, Optional, Tuple

from __experimental__._features.late_bound_arg_defaults import _defer, _evaluate_late_binding

# ======== We'll be benchmarking the desugared version of this:

# def example(
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


# ======== The functions that do the "benchmarking".


def run_timer(iterations: int) -> None:
    import timeit
    from functools import partial

    expected_result = (["Preceding args", 1, 1.0, "hello"], 4)

    for text, callback in (
        (f"With call:{' ' * 15}", example_called),
        ("With None sentinel idiom:", example_none_idiom),
    ):
        test_callback = partial(callback, 1)
        assert test_callback() == expected_result
        print(text, timeit.timeit(test_callback, number=iterations))


def profile_func(callback: Callable[..., object], iterations: int):
    for _ in range(iterations):
        callback(1)


def run_profiler(iterations: int):
    import cProfile

    for callback in ("example_called", "example_none_idiom"):
        print(f"=== Profiling for {callback}\n")
        cProfile.run(f"profile_func({callback}, {iterations})", f"log_{callback}.pstats")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Benchmark the late_bound_arg_defaults feature.",
    )
    parser.add_argument("-b", "--benchmark", action="store_true")
    parser.add_argument("-p", "--profile", action="store_true")
    parser.add_argument("-i", "--iterations", default=1_000_000, type=int)

    args = parser.parse_args()

    if not (args.benchmark or args.profile):
        msg = "Pick an option to run this with, either -b or -p."
        raise RuntimeError(msg)

    iterations = args.iterations
    print(f"Iterations = {iterations}")

    if args.benchmark:
        print("============ Timing ============")
        run_timer(iterations)

        # TODO: See if there's a way to make late_bound_arg_defaults faster somehow while using "pure" Python
        # because 20x slower is terrible.
        #
        # Iterations = 1,000,000
        # ============ Timing ============
        # With call:                2.823724805988604
        # With None sentinel idiom: 0.14172109999344684

    if args.profile:
        print("============ Profiling ============")
        run_profiler(iterations)


if __name__ == "__main__":
    raise SystemExit(main())
