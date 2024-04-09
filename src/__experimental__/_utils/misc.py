import functools
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec("P")
else:
    P = [TypeVar("P")]

T = TypeVar("T")

__all__ = ("copy_annotations",)


def copy_annotations(original_func: Callable[P, T]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    # Overrides annotations, thus lying, but it works for the final annotations that the *user* sees on the decorated func.
    @functools.wraps(original_func)
    def inner(new_func: Callable[P, T]) -> Callable[P, T]:
        return new_func

    return inner
