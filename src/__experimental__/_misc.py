from collections.abc import Callable
from typing import ParamSpec, TypeVar


_T = TypeVar("_T")
_P = ParamSpec("_P")

__all__ = ("copy_annotations",)


def copy_annotations(original_func: Callable[_P, _T]) -> Callable[[Callable[..., object]], Callable[_P, _T]]:
    """A decorator that copies the annotations from one function onto another.

    It may be a lie, but the lie can aid type checkers, IDEs, intellisense, etc.
    """

    def inner(new_func: Callable[..., object]) -> Callable[_P, _T]:
        # functools.wraps is overkill for this.
        try:
            new_func.__annotations__ = original_func.__annotations__
        except AttributeError:
            pass
        return new_func  # type: ignore # A lie.

    return inner
