from typing import Protocol, runtime_checkable

from __experimental__ import _peekable, _utils


def test_copy_annotations() -> None:
    @runtime_checkable
    class BaseProtocol(Protocol):
        def __call__(self, inp: int, *, out: str) -> str: ...

    def base(inp: int, *, out: str) -> str: ...

    @_utils.copy_annotations(base)  # Error expected; ignore.
    def derived(inp, *, out): ...  # Error expected; ignore.

    assert isinstance(derived, BaseProtocol)


def test_peekable() -> None:
    peekable_gen = _peekable.Peekable(i * 2 for i in range(20))

    assert not peekable_gen._cache
    assert peekable_gen.has_more()
    assert peekable_gen._cache

    assert peekable_gen.peek() == peekable_gen._cache[0]
    next(peekable_gen)
    assert not peekable_gen._cache

    for val, expected_val in zip((i * 2 for i in range(1, 20)), peekable_gen):
        assert val == expected_val
