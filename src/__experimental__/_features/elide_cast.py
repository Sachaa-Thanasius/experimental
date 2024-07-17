"""An implementation of eliding typing cast calls in pure Python."""

import ast

from __experimental__._ast_helpers import ScopeTracker, compare_asts
from __experimental__._core import _ExperimentalFeature, _Transformers
from __experimental__._misc import copy_annotations


class CastElisionTransformer(ScopeTracker):
    """An AST transformer that removes calls to `typing.cast` or `typing_extensions.cast`.

    Reference for tracking scopes within an AST: https://stackoverflow.com/a/55834093
    """

    def __init__(self) -> None:
        super().__init__()
        self.typing_imports = frozenset({"typing", "typing_extensions"})
        self.used_at: list[tuple[str, str, int]] = []

    def visit_Import(self, node: ast.Import) -> ast.AST:
        self.scopes.update({(a.asname or a.name): a.name for a in node.names if a.name in self.typing_imports})
        return self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.AST:
        source = node.module

        if node.level == 0 and (source in self.typing_imports):
            self.scopes.update({a.asname or a.name: f"{source}.{a.name}" for a in node.names if a.name == "cast"})

        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        match node:
            case ast.Call(func=ast.Name(id=name), args=[_, right_side]) if imported_name := self.scopes.get(name):
                self.used_at.append((imported_name, name, node.lineno))
                mod_node = right_side

            case ast.Call(
                func=ast.Attribute(value=ast.Name(id=mod_name), attr="cast"), args=[_, right_side]
            ) if imported_name := self.scopes.get(mod_name):
                self.used_at.append((f"{imported_name}.cast", f"{mod_name}.cast", node.lineno))
                mod_node = right_side

            case _:
                mod_node = node

        return self.generic_visit(mod_node)

    def visit_Assign(self, node: ast.Assign) -> ast.AST | None:
        match node:
            case ast.Assign(
                targets=[left_side],
                value=ast.Call(func=ast.Name(id=name), args=[_, right_side]),
            ) if (imported_name := self.scopes.get(name)) and compare_asts(left_side, right_side):
                self.used_at.append((imported_name, name, node.lineno))
                return None

            case ast.Assign(
                targets=[left_side],
                value=ast.Call(func=ast.Attribute(value=ast.Name(id=mod_name), attr="cast"), args=[_, right_side]),
            ) if (imported_name := self.scopes.get(mod_name)) and compare_asts(left_side, right_side):
                self.used_at.append((f"{imported_name}.cast", f"{mod_name}.cast", node.lineno))
                return None

            case _:
                return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    """Walk through an AST and replace calls to `typing.cast` or `typing_extensions.cast` with the original value."""

    return ast.fix_missing_locations(CastElisionTransformer().visit(tree))


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
    """Convert source code with elided cast calls to a valid AST.

    Notes
    -----
    The runtime annotations for this method are a bit off; see `ast.parse`, the function this wraps, for details about
    the actual signature.
    """

    return transform_ast(
        ast.parse(
            source,
            filename,
            mode,
            type_comments=type_comments,
            feature_version=feature_version,
        )
    )


FEATURE = _ExperimentalFeature(
    "elide_cast",
    "2024.05.03",
    transformers=_Transformers(None, None, transform_ast, parse),
    reference="Discussions about the runtime cost of typing.cast.",
)
