from experimental import late_bound_arg_defaults

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

def test_call_after_experimental_load():
    z, a, b, c, d = example_func(2.0, 3)
    assert z == 2.0
    assert a == 3
    assert b == [3, 3, 3]
    assert c == {"3": [3, 3, 3]}
    assert d == "2.0{'3': [3, 3, 3]}"