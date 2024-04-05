from __future__ import annotations

import ast
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
import tokenize
from collections.abc import Callable, Iterable, Sequence
from importlib._bootstrap import _call_with_frames_removed  # type: ignore # Has to come from the source.
from io import BytesIO
from typing import TYPE_CHECKING, NamedTuple, ParamSpec, Protocol, TypeAlias, TypeVar, cast

from __experimental__._lazy_import import lazy_module_import
from __experimental__.features import _inline_import, _late_bound_arg_defaults

if TYPE_CHECKING:
    import types

    from typing_extensions import Buffer as ReadableBuffer

# Copied from _typeshed - this and ReadableBuffer were marked as stable.
StrPath: TypeAlias = str | os.PathLike[str]

T = TypeVar("T")
P = ParamSpec("P")


class _CurryProtocol(Protocol):
    def __call__(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...


_call_with_frames_removed = cast(_CurryProtocol, _call_with_frames_removed)


__all__ = ("all_feature_names", "lazy_module_import", "late_bound_arg_defaults", "inline_import")

all_feature_names = ("late_bound_arg_defaults", "inline_import")


class _Transformers(NamedTuple):
    source: Callable[[str], str] | None = None
    token: Callable[[Iterable[tokenize.TokenInfo]], Iterable[tokenize.TokenInfo]] | None = None
    ast: Callable[[ast.AST], ast.Module] | None = None
    parse: Callable[[str], ast.Module] | None = None


class _ExperimentalFeature:
    """A feature class that attempts to emulate `__future__._Feature` to some degree."""

    def __init__(self, name: str, date_added: str, *, transformers: _Transformers, reference: str | None = None):
        self.name = name
        self.date_added = date_added
        self.transformers = transformers
        self.reference = reference

    def __repr__(self) -> str:
        maybe_ref = f", reference={self.reference}" if self.reference else ""
        return f"_ExperimentalFeature(name={self.name}, date_added={self.date_added}{maybe_ref})"


late_bound_arg_defaults = _ExperimentalFeature(
    "late_bound_arg_defaults",
    "2024.03.30",
    transformers=_Transformers(
        _late_bound_arg_defaults.transform_source,
        _late_bound_arg_defaults.transform_tokens,
        _late_bound_arg_defaults.transform_ast,
        _late_bound_arg_defaults.parse,
    ),
    reference="https://peps.python.org/pep-0671/",
)

inline_import = _ExperimentalFeature(
    "inline_import",
    "2024.04.04",
    transformers=_Transformers(
        _inline_import.transform_source,
        _inline_import.transform_tokens,
        _inline_import.transform_ast,
        _inline_import.parse,
    ),
    reference="https://github.com/ioistired/import-expression-parser",
)


class _ExperimentalFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        # Ensure that this is a source file we can actually rewrite. Inspired by pytest's finder.
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
    @staticmethod
    def _find_experimental_flags(tokens: list[tokenize.TokenInfo]) -> set[str]:
        collected_flags: set[str] = set()
        for (i, first), second, third in zip(enumerate(tokens), tokens[1:], tokens[2:], strict=False):
            if (
                first.type == tokenize.NAME
                and first.string == "from"
                and second.type == tokenize.NAME
                and second.string == "__experimental__"
                and third.type == tokenize.NAME
                and third.string == "import"
            ):
                temp = i
                fourth = tokens[temp + 3]
                while fourth.exact_type in {tokenize.NAME, tokenize.COMMA}:
                    if fourth.type == tokenize.NAME and fourth.string != "as":
                        collected_flags.add(fourth.string)
                    temp += 1
                    fourth = tokens[temp + 3]
        return collected_flags

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType | None:
        """Use default semantics for module creation, for now."""

    def source_to_code(  # type: ignore
        self,
        data: ReadableBuffer,
        path: ReadableBuffer | StrPath,
        *,
        _optimize: int = -1,
    ) -> types.CodeType:
        source = importlib.util.decode_source(data)
        tokens = list(tokenize.tokenize(BytesIO(source.encode()).readline))

        # Check if the code imports anything from __experimental__.
        collected_flags: set[str] = self._find_experimental_flags(tokens)
        features_to_activate: list[_ExperimentalFeature] = []

        # Collect features to activate.
        for found_flag in collected_flags:
            if found_flag in all_feature_names:
                features_to_activate.append(globals()[found_flag])

        # If no flags are set, do normal compilation.
        if not features_to_activate:
            return _call_with_frames_removed(compile, data, path, "exec", dont_inherit=True, optimize=_optimize)

        # Apply relevant token transformations.
        for feature in features_to_activate:
            if feature.transformers.token:
                tokens = list(feature.transformers.token(tokens))

        source = tokenize.untokenize(tokens)

        # Apply relevant AST transformations.
        tree: ast.Module = _call_with_frames_removed(
            compile,
            source,
            path,
            "exec",
            dont_inherit=True,
            optimize=_optimize,
            flags=ast.PyCF_ONLY_AST,
        )

        for feature in features_to_activate:
            if feature.transformers.ast:
                tree = feature.transformers.ast(tree)

        # Always perform the normal compilation step.
        return _call_with_frames_removed(compile, tree, path, "exec", dont_inherit=True, optimize=_optimize)


_EXPERIMENTAL_FINDER = _ExperimentalFinder()


def install() -> None:
    if _EXPERIMENTAL_FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _EXPERIMENTAL_FINDER)


def uninstall() -> None:
    try:
        sys.meta_path.remove(_EXPERIMENTAL_FINDER)
    except ValueError:
        pass
