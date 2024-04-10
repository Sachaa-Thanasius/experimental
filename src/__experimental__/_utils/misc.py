import functools
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from typing_extensions import ParamSpec

    class _GenericAlias:
        def __init__(self, *args: object, **kwargs: object): ...
        def __init_subclass__(cls, **kwargs: object) -> None: ...

    P = ParamSpec("P")
else:
    from typing import _GenericAlias

    P = [TypeVar("P")]

T = TypeVar("T")

__all__ = ("copy_annotations",)


def copy_annotations(original_func: Callable[P, T]) -> Callable[[Callable[P, T]], Callable[P, T]]:
    # Overrides annotations, thus lying, but it works for the final annotations that the *user* sees on the decorated func.
    @functools.wraps(original_func)
    def inner(new_func: Callable[P, T]) -> Callable[P, T]:
        return new_func

    return inner


# Hack for placeholders for special typing generic aliases that don't exist at runtime.
# Modified from this: https://discuss.python.org/t/using-get-type-hints-with-cyclic-imports/44828/6
class _PlaceholderGenericAlias(_GenericAlias, _root=True):
    def __repr__(self):
        return f"Circular import placeholder for {super().__repr__()}"


class PlaceholderMeta(type):
    def __getitem__(self, item: object):
        return _PlaceholderGenericAlias(self, item)

    def __repr__(self):
        return f"Circular import placeholder for {super().__repr__()}"
