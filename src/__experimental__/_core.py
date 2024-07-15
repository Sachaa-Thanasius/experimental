"""The main residence of the feature objects and overarching import logic.

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

from __experimental__._token_helpers import get_imported_experimental_flags
from __experimental__._typing_compat import ReadableBuffer, Self, override


if TYPE_CHECKING:
    from typing import ParamSpec, Protocol, TypeVar

    T = TypeVar("T")
    P = ParamSpec("P")

    class _CurryProtocol(Protocol):
        def __call__(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...

    # Hack to inform type-checker of annotations.
    _call_with_frames_removed: _CurryProtocol = _call_with_frames_removed  # noqa: PLW0127


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
    ) -> None:
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

    def __init__(
        self,
        name: str,
        date_added: str,
        *,
        transformers: _Transformers,
        reference: str | None = None,
    ) -> None:
        self.name: str = name
        self.date_added: str = date_added
        self.transformers: _Transformers = transformers
        self.reference: str | None = reference
        self._registry[name] = self

    @override
    def __repr__(self) -> str:
        maybe_ref = f", reference={self.reference}" if self.reference else ""
        return f"_ExperimentalFeature(name={self.name}, date_added={self.date_added}{maybe_ref})"


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

        # Get the feature names that the code imports from __experimental__.
        collected_flags = get_imported_experimental_flags(source)
        features_to_activate = tuple(
            _ExperimentalFeature._registry[flag]
            for flag in collected_flags.intersection(_ExperimentalFeature._registry.keys())
        )

        # If no flags are set, do normal compilation.
        if not features_to_activate:
            return _call_with_frames_removed(compile, data, path, "exec", dont_inherit=True, optimize=_optimize)

        # Apply token transformations.
        tokens = tokenize.tokenize(BytesIO(data).readline)

        for feature in features_to_activate:
            if feature.transformers.token_hook:
                tokens = feature.transformers.token_hook(tokens)

        # The source should be syntactically valid now as far as we're concerned.
        source = tokenize.untokenize(tokens)

        # Apply AST transformations.
        tree = _call_with_frames_removed(ast.parse, source, path, "exec")

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
