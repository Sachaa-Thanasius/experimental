"""The main residence of the feature objects and overarching import logic.

TODO: Consider making the features even more plugin-like.
"""

import ast
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
import tokenize
from importlib._bootstrap import _call_with_frames_removed  # type: ignore # Has to come from importlib.
from io import BytesIO
from typing import TYPE_CHECKING, Callable, ClassVar, Dict, Iterable, Optional, Sequence, Set, Tuple, TypeVar, Union

from __experimental__._features import (
    inline_import as _inline_import,
    late_bound_arg_defaults as _late_bound_arg_defaults,
    lazy_import as _lazy_import,
)
from __experimental__._utils.token_helpers import get_imported_experimental_flags

if TYPE_CHECKING:
    import types
    from typing import Protocol, cast

    from typing_extensions import Buffer as ReadableBuffer, ParamSpec, Self, TypeAlias

    T = TypeVar("T")
    P = ParamSpec("P")

    class _CurryProtocol(Protocol):
        def __call__(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...

    _call_with_frames_removed = cast(_CurryProtocol, _call_with_frames_removed)
else:

    class Self:
        pass

    class TypeAlias:
        pass

    ReadableBuffer = bytes


# Copied from _typeshed - this and ReadableBuffer were marked as stable.
StrPath: TypeAlias = "Union[str, os.PathLike[str]]"


class _Transformers:
    __slots__ = ("source_hook", "token_hook", "ast_hook", "parse")

    def __init__(
        self,
        source_hook: Optional[Callable[[str], str]] = None,
        token_hook: Optional[Callable[[Iterable[tokenize.TokenInfo]], Iterable[tokenize.TokenInfo]]] = None,
        ast_hook: Optional[Callable[[ast.AST], ast.Module]] = None,
        parse: Optional[Callable[[str], ast.Module]] = None,
    ):
        self.source_hook = source_hook
        self.token_hook = token_hook
        self.ast_hook = ast_hook
        self.parse = parse


class _ExperimentalFeature:
    """A feature class that attempts to emulate `__future__._Feature` to some degree.

    Attributes
    ----------
    name: str
        The name of the feature.
    date_added: str
        A date in the format YYYY.MM.DD for when the feature was added to this package.
    transformers: _Transformers
        A collection of transformers used to implement the feature.
    reference: str | None, default=None
        A link to the inspiration or reference material for the feature, should it exist.
    """

    __slots__ = ("name", "date_added", "transformers", "reference")
    _registry: ClassVar[Dict[str, Self]] = {}

    def __init__(self, name: str, date_added: str, *, transformers: _Transformers, reference: Optional[str] = None):
        self.name: str = name
        self.date_added: str = date_added
        self.transformers: _Transformers = transformers
        self.reference: Optional[str] = reference
        self._registry[name] = self

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

lazy_import = _ExperimentalFeature(
    "lazy_import",
    "2024.04.10",
    transformers=_Transformers(
        None,
        None,
        _lazy_import.transform_ast,
        _lazy_import.parse,
    ),
    reference="https://peps.python.org/pep-0690/",
)


class _ExperimentalFinder(importlib.abc.MetaPathFinder):
    def find_spec(
        self,
        fullname: str,
        path: Optional[Sequence[str]],
        target: "Optional[types.ModuleType]" = None,
    ) -> Optional[importlib.machinery.ModuleSpec]:
        # Ensure that this is a source file we can actually rewrite.
        # Method modified slightly from the pytest AssertionRewriteHook finding logic.
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
    def create_module(self, spec: importlib.machinery.ModuleSpec) -> "Optional[types.ModuleType]":
        """Use default semantics for module creation, for now."""

    # Might need a typeshed question. SourceFileLoader generally only gets bytes as data.
    def source_to_code(  # type: ignore
        self,
        data: ReadableBuffer,
        path: Union[ReadableBuffer, StrPath],
        *,
        _optimize: int = -1,
    ) -> "types.CodeType":
        source = importlib.util.decode_source(data)

        # Check if the code imports anything from __experimental__ and collect imported features.
        collected_flags: Set[str] = get_imported_experimental_flags(source)
        features_to_activate: Tuple[_ExperimentalFeature, ...] = tuple(
            _ExperimentalFeature._registry[flag]
            for flag in collected_flags.intersection(_ExperimentalFeature._registry.keys())
        )

        # If no flags are set, do normal compilation.
        if not features_to_activate:
            return _call_with_frames_removed(compile, data, path, "exec", dont_inherit=True, optimize=_optimize)

        # Apply relevant token transformations.
        tokens = tokenize.tokenize(BytesIO(data).readline)

        for feature in features_to_activate:
            if feature.transformers.token_hook:
                tokens = feature.transformers.token_hook(tokens)

        # The source should be syntactically valid now as far as we're concerned.
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
            if feature.transformers.ast_hook:
                tree = feature.transformers.ast_hook(tree)

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
