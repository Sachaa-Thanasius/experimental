"""A way to lazy-load blocks of regular import statements."""

import ast
import importlib.abc
import importlib.machinery
import importlib.util
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

from __experimental__._utils.misc import copy_annotations

if TYPE_CHECKING:
    import types

    from typing_extensions import Buffer as ReadableBuffer
else:
    ReadableBuffer = bytes


__all__ = ("lazy_module_import", "transform_ast", "parse")


class _LazyFinder(importlib.abc.MetaPathFinder):
    """A finder that delegates finding to the rest of the meta path and changes the found spec's loader.

    It currently wraps the actual loader with `importlib.util.LazyLoader`.
    """

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: "types.ModuleType | None" = None,
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
            msg = "missing loader"
            raise ImportError(msg, name=spec.name)

        spec.loader = importlib.util.LazyLoader(spec.loader)
        return spec


_LAZY_FINDER = _LazyFinder()


def lazy_install() -> None:
    if _LAZY_FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _LAZY_FINDER)


def lazy_uninstall() -> None:
    try:
        sys.meta_path.remove(_LAZY_FINDER)
    except ValueError:
        pass


class lazy_module_import:
    """A context manager that causes imports occuring within it to occur lazily.

    Notes
    -----
    This class is dead simple: It adds a special finder to sys.meta_path and then removes it. That finder
    wraps the loaders of imported modules with importlib.util.LazyLoader.
    """

    def __enter__(self):
        lazy_install()
        return self

    def __exit__(self, *exc: object):
        lazy_uninstall()


class LazyImportTransformer(ast.NodeTransformer):
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

        aliases = [ast.alias("lazy_install", "@lazy_install"), ast.alias("lazy_uninstall", "@lazy_uninstall")]
        imports = ast.ImportFrom(module="__experimental__._features.lazy_import", names=aliases, level=0)
        install_expr = ast.Expr(value=ast.Call(func=ast.Name(id="@lazy_install", ctx=ast.Load()), args=[], keywords=[]))
        uninstall_expr = ast.Expr(
            value=ast.Call(func=ast.Name(id="@lazy_uninstall", ctx=ast.Load()), args=[], keywords=[]),
        )

        node.body.insert(position, imports)
        node.body.insert(position + 1, install_expr)
        node.body.append(uninstall_expr)

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    return ast.fix_missing_locations(LazyImportTransformer().visit(tree))


# Some of the parameter annotations are too narrow or wide, but they should be "overriden" by this decorator.
@copy_annotations(ast.parse)  # type: ignore
def parse(
    source: str | ReadableBuffer,
    filename: str = "<unknown>",
    mode: str = "exec",
    *,
    type_comments: bool = False,
    feature_version: tuple[int, int] | None = None,
) -> ast.Module:
    return transform_ast(
        ast.parse(
            source,
            filename,
            mode,
            type_comments=type_comments,
            feature_version=feature_version,
        ),
    )
