from collections.abc import Callable
from typing import ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")

__all__ = ("copy_annotations",)


def copy_annotations(original_func: Callable[P, T]) -> Callable[[Callable[..., object]], Callable[P, T]]:
    """A decorator that applies the annotations from one function onto another.

    It can be a lie, but it aids the type checker and any IDE intellisense.
    """

    def inner(new_func: Callable[..., object]) -> Callable[P, T]:
        # functools.wraps is overkill for this.
        try:
            new_func.__annotations__ = original_func.__annotations__
        except AttributeError:
            pass
        return new_func  # type: ignore # A lie.

    return inner
