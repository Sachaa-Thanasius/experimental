from __future__ import annotations

import ast
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from collections.abc import Callable, Sequence
from importlib._bootstrap import _call_with_frames_removed  # type: ignore # Has to come from the source.
from typing import TYPE_CHECKING, ClassVar, ParamSpec, Protocol, TypeAlias, TypeVar, cast

from ._late_bound_arg_defaults import _modify_ast, _modify_source, parse as parse_into_late_bound_defaults
from ._lazy_import import lazy_module_import

if TYPE_CHECKING:
    import types

    from typing_extensions import Buffer as ReadableBuffer, Self

# Copied from _typeshed - this and ReadableBuffer were marked as stable.
StrPath: TypeAlias = str | os.PathLike[str]

T = TypeVar("T")
P = ParamSpec("P")


class _CurryProtocol(Protocol):
    def __call__(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...


_call_with_frames_removed = cast(_CurryProtocol, _call_with_frames_removed)

# TODO: Benchmark to see if removing as many annotation-related imports at runtime as possible makes a difference.

__all__ = ("late_bound_arg_defaults", "lazy_module_import")


class _ExperimentalFeature:
    """A feature class that attempts to emulate `__future__._Feature` to some degree."""

    feature_register: ClassVar[dict[str, Self]] = {}

    def __init__(
        self,
        name: str,
        date_added: str,
        transformer: Callable[..., ast.Module],
        *,
        reference: str | None = None,
    ):
        self.name = name
        self.date_added = date_added
        self.transformer = transformer
        self.reference = reference
        self.feature_register[name] = self

    def __repr__(self) -> str:
        maybe_ref = f", reference={self.reference}" if self.reference else ""
        return f"_ExperimentalFeature(name={self.name}, date_added={self.date_added}{maybe_ref})"


late_bound_arg_defaults = _ExperimentalFeature(
    "late_bound_arg_defaults",
    "2024.03.30",
    parse_into_late_bound_defaults,
    reference="https://peps.python.org/pep-0671/",
)


class _ExperimentalImportCollector(ast.NodeVisitor):
    def __init__(self):
        self.experimental_flags: set[str] = set()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # TODO: Force more conditions on where the imports must be, e.g. at the top of a file after future imports.
        if node.module == "__experimental__" and node.level == 0:
            self.experimental_flags.update(alias.name for alias in node.names if alias.name[0] != "_")
        return self.generic_visit(node)


class _ExperimentalFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        # Source for this way of finding: _pytest.assertion.rewrite.
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)

        if (
            spec is None
            or spec.origin is None
            or not isinstance(spec.loader, importlib.machinery.SourceFileLoader)
            or not os.path.exists(spec.origin)  # noqa: PTH110
        ):
            return None

        return importlib.util.spec_from_file_location(
            fullname,
            spec.origin,
            loader=_ExperimentalLoader(fullname, spec.origin),
            submodule_search_locations=spec.submodule_search_locations,
        )


class _ExperimentalLoader(importlib.machinery.SourceFileLoader):
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
        """Use default semantics for module creation, for now."""

    def source_to_code(  # type: ignore
        self,
        data: ReadableBuffer,  # Should always be a readable buffer in the case of a source file, I think.
        path: ReadableBuffer | StrPath,
        *,
        _optimize: int = -1,
    ) -> types.CodeType:
        # Get the AST for the importing module.

        # TODO: Get rid of this hack somehow. Find a way to identify the imports without needing a node visitor.
        # That way, the indicator that the source needs modifying before AST parsing doesn't have to be a SyntaxError.
        expect_late_bound_flag = False
        try:
            tree: ast.Module = _call_with_frames_removed(
                compile,
                data,
                path,
                "exec",
                dont_inherit=True,
                optimize=_optimize,
                flags=ast.PyCF_ONLY_AST,
            )
        except SyntaxError:
            modified_data = _modify_source(importlib.util.decode_source(data))
            expect_late_bound_flag = True
            tree: ast.Module = _call_with_frames_removed(
                compile,
                modified_data,
                path,
                "exec",
                dont_inherit=True,
                optimize=_optimize,
                flags=ast.PyCF_ONLY_AST,
            )

        # Check if the code imports anything from __experimental__.
        checker = _ExperimentalImportCollector()
        checker.visit(tree)
        found_flags = set(checker.experimental_flags)
        activated_features: set[str] = set()

        # Apply transformations accordingly.
        if found_flags:
            # This needs special-casing since it performs a str to AST transform instead of an AST to AST one.
            if "late_bound_arg_defaults" in found_flags:
                if expect_late_bound_flag:
                    tree = _modify_ast(tree)
                else:
                    tree = late_bound_arg_defaults.transformer(ast.unparse(tree))
                activated_features.add("late_bound_arg_defaults")

            found_features = found_flags.intersection(_ExperimentalFeature.feature_register.keys())
            # Assume any features made in the future will do pure AST transformation for now.
            for feature_name in found_features:
                if feature_name in found_flags and feature_name not in activated_features:
                    tree = _ExperimentalFeature.feature_register[feature_name].transformer(tree)
                    activated_features.add(feature_name)

        # Always perform the normal compilation step.
        return _call_with_frames_removed(compile, tree, path, "exec", dont_inherit=True, optimize=_optimize)


_EXPERIMENTAL_FINDER = _ExperimentalFinder()


def install() -> None:
    if _EXPERIMENTAL_FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _EXPERIMENTAL_FINDER)


def uninstall() -> None:
    if _EXPERIMENTAL_FINDER in sys.meta_path:
        sys.meta_path.remove(_EXPERIMENTAL_FINDER)
