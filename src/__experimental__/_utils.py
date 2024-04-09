import functools
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    P = ParamSpec("P")
else:
    P = [TypeVar("P")]

T = TypeVar("T")


def copy_annotations(original_func: Callable[P, T]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    @functools.wraps(original_func)
    def inner(new_func: Callable[P, T]) -> Callable[P, T]:
        return new_func

    return inner
