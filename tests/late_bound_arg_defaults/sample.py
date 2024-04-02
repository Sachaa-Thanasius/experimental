from __experimental__ import late_bound_arg_defaults


def example_func(
    z: float,
    a: int = 1,
    b: list[int] => ([a] * a),
    /,
    c: dict[str, int] => ({str(a): b}),
    *,
    d: str => (str(z) + str(c)),
) -> str:
    return z, a, b, c, d
