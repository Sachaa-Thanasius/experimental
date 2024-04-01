from __future__ import annotations

import ast
import importlib.machinery
import importlib.util
import sys

from ._late_bound_arg_defaults_impl import transform as transform_into_late_bound_defaults

DEBUG = False

if DEBUG:
    import os
    import types
    from collections.abc import Callable
    from typing import ClassVar, ParamSpec, TypeAlias, TypeVar

    from typing_extensions import Buffer, Self

    # Copied from _typeshed - they were marked as stable.
    ReadableBuffer: TypeAlias = Buffer
    StrPath: TypeAlias = str | os.PathLike[str]

    T = TypeVar("T")
    P = ParamSpec("P")

__all__ = ("late_bound_arg_defaults",)


def _call_with_frames_removed(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Calls a function while removing itself and that function call from tracebacks, should any be generated.

    Notes
    -----
    This is a CPython-specific hack, I think. Probably will break at some point if a better mechanism is implemented.
    """

    return func(*args, **kwargs)


class _ExperimentalFeature:
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
    transform_into_late_bound_defaults,
    reference="https://peps.python.org/pep-0671/",
)


class _ExperimentalImportCollector(ast.NodeVisitor):
    def __init__(self):
        self.experimental_flags: set[str] = set()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # TODO: Force more conditions on where the imports must be, e.g. at the top of a file after future imports.
        if node.module == "experimental" and node.level == 0:
            self.experimental_flags.update(alias.name for alias in node.names if alias.name[0] != "_")
        return self.generic_visit(node)


class _ExperimentalSourceFileLoader(importlib.machinery.SourceFileLoader):
    def source_to_code(  # type: ignore
        self,
        data: ReadableBuffer | str | ast.Module | ast.Expression | ast.Interactive,
        path: ReadableBuffer | StrPath,
        *,
        _optimize: int = -1,
    ) -> types.CodeType:
        # Get the AST for the importing module.
        tree: ast.Module = _call_with_frames_removed(
            compile,
            data,
            path,
            "exec",
            dont_inherit=True,
            optimize=_optimize,
            flags=ast.PyCF_ONLY_AST,
        )

        # Check if the code imports anything from experimental.
        checker = _ExperimentalImportCollector()
        checker.visit(tree)
        found_flags = set(checker.experimental_flags)
        activated_features: set[str] = set()

        # Apply transformations accordingly.
        if found_flags:
            # This needs special-casing since it performs a str to AST transform instead of an AST to AST one.
            if "late_bound_arg_defaults" in found_flags:
                tree = late_bound_arg_defaults.transformer(ast.unparse(tree))
                activated_features.add("late_bound_arg_defaults")

            # Assume any features made in the future will do pure AST transformation for now.
            for feature_name, feature in _ExperimentalFeature.feature_register.items():
                if feature_name in found_flags and feature_name not in activated_features:
                    tree = feature.transformer(tree)
                    activated_features.add(feature_name)

        # Always perform the normal compilation step.
        return _call_with_frames_removed(compile, tree, path, "exec", dont_inherit=True, optimize=_optimize)


def install() -> None:
    # Almost exactly the same as the default FileFinder hook on startup, with one difference: the loader for source files.

    extensions = (importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES)
    source = (_ExperimentalSourceFileLoader, importlib.machinery.SOURCE_SUFFIXES)
    bytecode = (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES)

    # The FileFinder hook should always be the last one in theory.
    sys.path_hooks[-1] = importlib.machinery.FileFinder.path_hook(extensions, source, bytecode)

    # In theory, this needs to be reset for the new hook to take effect
    sys.path_importer_cache.clear()
