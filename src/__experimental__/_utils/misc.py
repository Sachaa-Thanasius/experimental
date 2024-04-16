import functools
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

_T = TypeVar("_T")
_P = ParamSpec("_P")

__all__ = ("copy_annotations",)


def copy_annotations(original_func: Callable[_P, _T]) -> Callable[[Callable[..., Any]], Callable[_P, _T]]:
    """A decorator that applies the annotations from one function onto another.

    It can be a lie, but it aids the type checker and any IDE intellisense.
    """

    def inner(new_func: Callable[..., Any]) -> Callable[_P, _T]:
        return functools.update_wrapper(new_func, original_func, ("__annotations__"))  # type: ignore

    return inner
