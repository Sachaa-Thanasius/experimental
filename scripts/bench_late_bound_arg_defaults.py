"""A small script for timing the late bound arg defaults against the normal sentinel idiom."""

from collections.abc import Callable

from __experimental__._features.late_bound_arg_defaults import DEFER_MARKER

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
    c: list[object] = DEFER_MARKER('["Preceding args", a, b, ex]'),  # type: ignore # noqa: B008
    d: bool = False,
    e: int = DEFER_MARKER("len(c)"),  # type: ignore
) -> tuple[list[object], int]:
    if type(c) is DEFER_MARKER:
        c = ["Preceding args", a, b, ex]
    if type(e) is DEFER_MARKER:
        e = len(c)

    return c, e


def example_none_idiom(
    a: int,
    b: float = 1.0,
    /,
    ex: str = "hello",
    *,
    c: list[object] | None = None,
    d: bool = False,
    e: int | None = None,
) -> tuple[list[object], int]:
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

    if args.profile:
        print("============ Profiling ============")
        run_profiler(iterations)


if __name__ == "__main__":
    raise SystemExit(main())
