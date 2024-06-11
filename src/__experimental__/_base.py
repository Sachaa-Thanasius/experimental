"""The main residence of the feature objects and overarching import logic.

TODO: Consider making the features even more plugin-like.
TODO: Figure out how to do one pass instead of multiple for the token and AST transformations.
    See pyupgrade for inspiration.
TODO: Switch to working on a list of tokens instead of a generator. That'll remove some complexity and allow bigger
    transformations.
"""

import ast
import importlib.machinery
import importlib.util
import os
import sys
import tokenize
import types
from collections.abc import Callable, Iterable
from importlib._bootstrap import _call_with_frames_removed  # type: ignore # Has to come from importlib, I think.
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar, TypeAlias

from __experimental__._features import (
    elide_cast as _elide_cast,
    inline_import as _inline_import,
    late_bound_arg_defaults as _late_bound_arg_defaults,
    lazy_import as _lazy_import,
)
from __experimental__._utils.token_helpers import get_imported_experimental_flags

if TYPE_CHECKING:
    from typing import Protocol, TypeVar

    from typing_extensions import Buffer as ReadableBuffer, ParamSpec, Self

    T = TypeVar("T")
    P = ParamSpec("P")

    class _CurryProtocol(Protocol):
        def __call__(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...

    # Hack to inform type-checker of annotations.
    _call_with_frames_removed: _CurryProtocol = _call_with_frames_removed  # noqa: PLW0127
else:

    class Self:
        pass

    ReadableBuffer = bytes


# Copied from _typeshed - this and ReadableBuffer were marked as stable.
StrPath: TypeAlias = str | os.PathLike[str]

CompilableAST: TypeAlias = ast.Module | ast.Expression | ast.Interactive


class _Transformers:
    __slots__ = ("source_hook", "token_hook", "ast_hook", "parse")

    def __init__(
        self,
        source_hook: Callable[[str], str] | None = None,
        token_hook: Callable[[Iterable[tokenize.TokenInfo]], Iterable[tokenize.TokenInfo]] | None = None,
        ast_hook: Callable[[CompilableAST], CompilableAST] | None = None,
        parse: Callable[..., ast.Module] | None = None,
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

    _registry: ClassVar[dict[str, Self]] = {}

    def __init__(self, name: str, date_added: str, *, transformers: _Transformers, reference: str | None = None):
        self.name: str = name
        self.date_added: str = date_added
        self.transformers: _Transformers = transformers
        self.reference: str | None = reference
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

elide_cast = _ExperimentalFeature(
    "elide_cast",
    "2024.05.03",
    transformers=_Transformers(
        None,
        None,
        _elide_cast.transform_ast,
        _elide_cast.parse,
    ),
    reference="Discussions about the runtime cost of typing.cast.",
)


class _ExperimentalLoader(importlib.machinery.SourceFileLoader):
    # Might need a typeshed question. SourceFileLoader generally only gets bytes as data, AFAIK.
    def source_to_code(  # type: ignore
        self,
        data: ReadableBuffer,
        path: ReadableBuffer | StrPath,
        *,
        _optimize: int = -1,
    ) -> types.CodeType:
        source = importlib.util.decode_source(data)

        # Check if the code imports anything from __experimental__ and collect imported features.
        collected_flags: set[str] = get_imported_experimental_flags(source)
        features_to_activate: tuple[_ExperimentalFeature, ...] = tuple(
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
        tree: CompilableAST = _call_with_frames_removed(ast.parse, source, path, "exec")

        for feature in features_to_activate:
            if feature.transformers.ast_hook:
                tree = feature.transformers.ast_hook(tree)

        # Always perform the normal compilation step.
        return _call_with_frames_removed(compile, tree, path, "exec", dont_inherit=True, optimize=_optimize)


# Almost the same as the results of importlib._bootstrap_external._get_supported_file_loaders(),
# except this gives our custom loader for source files.
_MODIFIED_SUPPORTED_FILE_LOADERS = [
    (importlib.machinery.ExtensionFileLoader, importlib.machinery.EXTENSION_SUFFIXES),
    (_ExperimentalLoader, importlib.machinery.SOURCE_SUFFIXES),
    (importlib.machinery.SourcelessFileLoader, importlib.machinery.BYTECODE_SUFFIXES),
]


def install_experimental_import_hook() -> None:
    for i, hook in enumerate(sys.path_hooks):
        if "FileFinder.path_hook" in hook.__qualname__:
            sys.path_hooks[i] = new_hook = importlib.machinery.FileFinder.path_hook(*_MODIFIED_SUPPORTED_FILE_LOADERS)
            new_hook._original_path_hook_for_FileFinder = hook  # type: ignore # Runtime attribute assignment.
            break


def uninstall_experimental_import_hook() -> None:
    for i, hook in enumerate(sys.path_hooks):
        if "FileFinder.path_hook" in hook.__qualname__ and hasattr(hook, "_original_path_hook_for_FileFinder"):
            sys.path_hooks[i] = hook._original_path_hook_for_FileFinder  # type: ignore # Runtime attribute access.
            break
