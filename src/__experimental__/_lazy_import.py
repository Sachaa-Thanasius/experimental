"""A way to lazy-load blocks of regular import statements."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import types


__all__ = ("lazy_module_import",)


class _LazyFinder(importlib.abc.MetaPathFinder):
    """A finder that delegates finding to the rest of the meta path and changes the found spec's loader.

    It currently wraps the actual loader with `importlib.util.LazyLoader`.
    """

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
        /,
    ) -> importlib.machinery.ModuleSpec:
        for finder in sys.meta_path:
            if finder != self:
                spec = finder.find_spec(fullname, path, target)
                if spec is not None:
                    break
        else:
            msg = f"No module named {fullname!r}"
            raise ModuleNotFoundError(msg, name=fullname)

        if spec.loader is None:
            raise ImportError("spec is missing a loader")

        spec.loader = importlib.util.LazyLoader(spec.loader)
        return spec


_LAZY_FINDER = _LazyFinder()


class lazy_module_import:
    """A context manager that causes imports occuring within it to occur lazily.

    Notes
    -----
    The implementation isn't that clever. It adds a special finder to sys.meta_path and then removes it. That finder
    wraps the loaders of imported modules with importlib.util.LazyLoader.
    """

    def __enter__(self):
        if _LAZY_FINDER not in sys.meta_path:
            sys.meta_path.insert(0, _LAZY_FINDER)
        return self

    def __exit__(self, *_: object):
        try:
            sys.meta_path.remove(_LAZY_FINDER)
        except ValueError:
            pass
