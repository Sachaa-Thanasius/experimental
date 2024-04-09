from typing import Protocol, runtime_checkable

from __experimental__._utils import misc, peekable


def test_peekable() -> None:
    peekable_gen = peekable.Peekable(i * 2 for i in range(20))

    assert not peekable_gen._cache
    assert peekable_gen.has_more()
    assert peekable_gen._cache

    assert peekable_gen.peek() == peekable_gen._cache[0]
    next(peekable_gen)
    assert not peekable_gen._cache

    for val, expected_val in zip((i * 2 for i in range(1, 20)), peekable_gen):
        assert val == expected_val
