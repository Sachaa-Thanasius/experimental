"""A partial implementation of lazy imports (PEP 690) with a context manager and module-wide in pure Python."""

import ast
import contextlib
import importlib.abc
import importlib.machinery
import importlib.util
import sys
import types
from collections.abc import Generator, Sequence
from typing import Any

from __experimental__._utils.misc import copy_annotations

__all__ = ("lazy_module_import", "transform_ast", "parse")


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
            # Technically eager to say it's missing for sure here, but seems like the simplest path.
            # References for regular behavior upon discovering a missing loader (CPython 3.11):
            # - importlib._bootstrap_external.PathFinder._get_spec
            # - importlib._bootstrap._load_unlocked
            # - importlib._bootstrap._exec

            msg = "missing loader"
            raise ImportError(msg, name=spec.name)

        spec.loader = importlib.util.LazyLoader(spec.loader)
        return spec


_LAZY_FINDER = _LazyFinder()


def install_lazy_import_hook() -> None:
    """Add a `_LazyFinder` singleton instance to `sys.meta_path`."""

    if _LAZY_FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _LAZY_FINDER)


def uninstall_lazy_import_hook() -> None:
    """Attempt to remove a `_LazyFinder` singleton instance from `sys.meta_path`."""

    try:
        sys.meta_path.remove(_LAZY_FINDER)
    except ValueError:
        pass


@contextlib.contextmanager
def lazy_module_import() -> Generator[None, Any, None]:
    """A context manager that causes imports occuring within it to occur lazily.

    Notes
    -----
    Implementation details: It adds a special finder to `sys.meta_path` and then removes it. That finder wraps the
    loaders of imported modules with `importlib.util.LazyLoader`.
    """

    install_lazy_import_hook()
    try:
        yield
    finally:
        uninstall_lazy_import_hook()


class LazyImportTransformer(ast.NodeTransformer):
    """An AST transformer that adds function calls to the start and end of a module to install and uninstall the
    lazy import hook, respectively.

    Notes
    -----
    This prepends the inserted function names with "@" to avoid colliding with names in user code.

    This doesn't insert the install until after all consecutive docstrings, __future__ imports, and
    __experimental__ imports.
    """

    def visit_Module(self, node: ast.Module) -> ast.AST:
        expect_docstring = True
        position = 0
        for sub_node in node.body:
            match sub_node:
                case ast.Expr(value=ast.Constant(value=str())) if expect_docstring:
                    expect_docstring = False
                case ast.ImportFrom(module="__future__" | "__experimental__", level=0):
                    pass
                case _:
                    break

            position += 1

        aliases = [
            ast.alias("install_lazy_import_hook", "@install_lazy_import_hook"),
            ast.alias("uninstall_lazy_import_hook", "@uninstall_lazy_import_hook"),
        ]
        imports = ast.ImportFrom(module="__experimental__._features.lazy_import", names=aliases, level=0)
        install_expr = ast.Expr(
            value=ast.Call(func=ast.Name(id="@install_lazy_import_hook", ctx=ast.Load()), args=[], keywords=[]),
        )
        uninstall_expr = ast.Expr(
            value=ast.Call(func=ast.Name(id="@uninstall_lazy_import_hook", ctx=ast.Load()), args=[], keywords=[]),
        )

        node.body.insert(position, imports)
        node.body.insert(position + 1, install_expr)
        node.body.append(uninstall_expr)

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    return ast.fix_missing_locations(LazyImportTransformer().visit(tree))


# Some of the parameter annotations are too narrow or wide, but they should be "overriden" by this decorator.
@copy_annotations(ast.parse)
def parse(
    source: str | bytes,
    filename: str = "<unknown>",
    mode: str = "exec",
    *,
    type_comments: bool = False,
    feature_version: tuple[int, int] | None = None,
) -> ast.Module:
    """Convert source code to a valid AST with module-wide lazy imports enabled.

    Notes
    -----
    The runtime annotations for this method are a bit off; see `ast.parse`, the function this wraps, for details about the
    actual signature.
    """

    return transform_ast(
        ast.parse(
            source,
            filename,
            mode,
            type_comments=type_comments,
            feature_version=feature_version,
        ),
    )
