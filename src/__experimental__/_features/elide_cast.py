"""An implementation of eliding typing cast calls in pure Python."""

import ast
from collections import ChainMap
from types import MappingProxyType
from typing import TYPE_CHECKING

from __experimental__._utils.misc import copy_annotations

if TYPE_CHECKING:
    from typing_extensions import Buffer as ReadableBuffer
else:
    ReadableBuffer = bytes

__all__ = ("transform_ast", "parse")


# ======== AST transformation.


class CastElisionTransformer(ast.NodeTransformer):
    """An AST transformer that removes calls to `typing.cast` or `typing_extensions.cast`.

    Reference for tracking scopes within an AST: https://stackoverflow.com/a/55834093
    """

    typing_imports = frozenset({"typing", "typing_extensions"})

    def __init__(self):
        self.scopes: ChainMap[str, str | None] = ChainMap()
        self.used_at: list[tuple[str, str, int]] = []

    def _visit_Func(self, node: ast.AST) -> ast.AST:
        self.scopes = self.scopes.new_child()
        mod_node = self.generic_visit(node)
        self.scopes = self.scopes.parents
        return mod_node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return self._visit_Func(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._visit_Func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._visit_Func(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.scopes = self.scopes.new_child(MappingProxyType({}))  # type: ignore
        mod_node = self.generic_visit(node)
        self.scopes = self.scopes.parents
        return mod_node

    def visit_Import(self, node: ast.Import) -> ast.AST:
        self.scopes.update({(a.asname or a.name): a.name for a in node.names if a.name in self.typing_imports})
        return node

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        source = node.module

        if node.level == 0 and (source in self.typing_imports):
            self.scopes.update({a.asname or a.name: f"{source}.{a.name}" for a in node.names if a.name == "cast"})

        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        match node:
            case ast.Call(func=ast.Name(id=name), args=[_, new_node]) if imported_name := self.scopes.get(name):
                self.used_at.append((imported_name, name, node.lineno))
                return new_node
            case ast.Call(
                func=ast.Attribute(value=ast.Name(id=mod_name), attr="cast"), args=[_, new_node]
            ) if imported_name := self.scopes.get(mod_name):
                self.used_at.append((f"{imported_name}.cast", f"{mod_name}.cast", node.lineno))
                return new_node
            case _:
                return node


def transform_ast(tree: ast.AST) -> ast.Module:
    """Walk through an AST and replace calls to `typing.cast` or `typing_extensions.cast` with just the original value."""

    return ast.fix_missing_locations(CastElisionTransformer().visit(tree))


# Some of the parameter annotations are too narrow or wide, but they should be "overriden" by this decorator.
@copy_annotations(ast.parse)
def parse(
    source: str | ReadableBuffer,
    filename: str = "<unknown>",
    mode: str = "exec",
    *,
    type_comments: bool = False,
    feature_version: tuple[int, int] | None = None,
) -> ast.Module:
    """Convert source code with elided cast calls to a valid AST. Has the same signature as `ast.parse`."""

    return transform_ast(
        ast.parse(
            source,
            filename,
            mode,
            type_comments=type_comments,
            feature_version=feature_version,
        )
    )
