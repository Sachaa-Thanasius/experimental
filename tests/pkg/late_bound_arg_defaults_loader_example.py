# Must be tested by installing `experimental` normally (not editable) and using the command
# `python -m tests.pkg.late_bound_arg_defaults_loader_example`,
# since pytest's ast transformer will attempt to do its work first and thus won't 
# recognize the following as valid syntax.

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

if __name__ == "__main__":
    raise SystemExit(test_call_after_experimental_load())