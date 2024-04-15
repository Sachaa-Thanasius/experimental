import functools
from collections.abc import Callable
from typing import ParamSpec, TypeVar

_T = TypeVar("_T")
_P = ParamSpec("_P")

__all__ = ("copy_annotations",)


def copy_annotations(original_func: Callable[_P, _T]) -> Callable[[Callable[_P, _T]], Callable[_P, _T]]:
    # Overrides annotations, thus lying, but it works for the final annotations that the *user* sees on the decorated func.
    @functools.wraps(original_func)
    def inner(new_func: Callable[_P, _T]) -> Callable[_P, _T]:
        return new_func

    return inner
