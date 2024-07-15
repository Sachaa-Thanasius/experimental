"""Compatibility module for re-exporting symbols from typing or typing-extensions as needed."""

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING


__all__ = ("ReadableBuffer", "Self", "override")


if sys.version_info >= (3, 12):  # pragma: >=3.12 cover
    from collections.abc import Buffer as ReadableBuffer
    from typing import override
elif TYPE_CHECKING:
    from typing_extensions import Buffer as ReadableBuffer, override
else:  # pragma: <3.12 cover
    from typing import TypeAlias, TypeVar

    ReadableBuffer: TypeAlias = bytes | bytearray | memoryview

    _CallableT = TypeVar("_CallableT", bound=Callable[..., object])

    def override(arg: _CallableT) -> _CallableT:
        try:
            arg.__override__ = True
        except AttributeError:  # pragma: no cover
            pass
        return arg


if sys.version_info >= (3, 11):  # pragma: >=3.11 cover
    from typing import Self
elif TYPE_CHECKING:
    from typing_extensions import Self
else:  # pragma: <3.11 cover

    class Self:
        pass
