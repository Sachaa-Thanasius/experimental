"""Compatibility module for re-exporting symbols from typing or typing-extensions as needed."""

import sys
from typing import TYPE_CHECKING


__all__ = ("Buffer", "Self")


if sys.version_info >= (3, 12):  # pragma: >=3.12 cover
    from collections.abc import Buffer
elif TYPE_CHECKING:
    from typing_extensions import Buffer
else:  # pragma: <3.12 cover
    from typing import TypeAlias

    Buffer: TypeAlias = bytes | bytearray | memoryview


if sys.version_info >= (3, 11):  # pragma: >=3.11 cover
    from typing import Self
elif TYPE_CHECKING:
    from typing_extensions import Self
else:  # pragma: <3.11 cover

    class Self:
        pass
