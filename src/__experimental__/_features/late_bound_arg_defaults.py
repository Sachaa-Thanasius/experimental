"""An implementation of late-bound function defaults (PEP 671) in "pure" Python."""

from __future__ import annotations

import ast
import ctypes
import sys
import tokenize
from collections.abc import Callable, Generator, Iterable
from io import BytesIO
from itertools import takewhile
from typing import TYPE_CHECKING, Optional, Tuple, Union

from __experimental__._utils.misc import copy_annotations
from __experimental__._utils.peekable import Peekable

if TYPE_CHECKING:
    from typing_extensions import Buffer as ReadableBuffer, TypeGuard


__all__ = ("transform_tokens", "transform_source", "transform_ast", "parse")


# === The parts that will actually do the work of implementing late binding argument defaults.


class _defer:
    """A class that holds the functions used for late binding in function signatures."""

    def __init__(self, func: Callable[..., object]):
        self.func = func

    def __call__(self, *args: object, **kwargs: object) -> object:
        return self.func(*args, **kwargs)


def _evaluate_late_binding(orig_locals: dict[str, object]) -> None:
    """Does the actual work of evaluating the late bindings and assigning them to the locals."""

    # Evaluate the late-bound function argument defaults (i.e. those with type `_defer`).
    new_locals = orig_locals.copy()
    for arg_name, arg_val in orig_locals.items():
        if isinstance(arg_val, _defer):
            new_locals[arg_name] = arg_val(*takewhile(lambda val: not isinstance(val, _defer), new_locals.values()))

    # Update the locals of the last frame with these new evaluated defaults.
    frame = sys._getframe(1)
    try:
        frame.f_locals.update(new_locals)
        # To my knowledge, PyPy doesn't support ctypes.pythonapi (or this sort of frame usage, really).
        # https://doc.pypy.org/en/latest/discussion/ctypes-implementation.html#discussion-and-limitations
        ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(frame), ctypes.c_int(0))
    finally:
        del frame


# === Token modification.


def transform_tokens(tokens: Iterable[tokenize.TokenInfo]) -> Generator[tokenize.TokenInfo, None, None]:
    """Replaces '=>' with '= _DEFER_MARKER' in the token stream to mark where 'defer' objects should go."""

    peekable_tokens_iter = Peekable(tokens)
    for tok in peekable_tokens_iter:
        if (
            tok.exact_type == tokenize.EQUAL
            and peekable_tokens_iter.has_more()
            and (peek := peekable_tokens_iter.peek()).exact_type == tokenize.GREATER
        ):
            yield tok

            # Replace this next token with a marker.
            next(peekable_tokens_iter)
            start_col, start_row = peek.start
            new_start = (start_col, start_row + 1)
            new_end = (start_col, start_row + 15)
            yield tokenize.TokenInfo(tokenize.NAME, "_DEFER_MARKER", new_start, new_end, tok.line)

            # Fix the positions of the rest of the tokens on the same line.
            old_row = tok.start[0]

            for ltr_tok in peekable_tokens_iter:
                if old_row != int(ltr_tok.start[0]):
                    yield ltr_tok
                    break

                new_start = (ltr_tok.start[0], ltr_tok.start[1] + 13)
                new_end = (ltr_tok.end[0], ltr_tok.end[1] + 13)
                yield ltr_tok._replace(start=new_start, end=new_end)

        else:
            yield tok


def transform_source(source: Union[str, ReadableBuffer]) -> str:
    """Replaces late binding tokens with valid Python, along with markers for the ast transformer."""

    if isinstance(source, str):
        source = source.encode("utf-8")
    stream = BytesIO(source)
    encoding, _ = tokenize.detect_encoding(stream.readline)
    stream.seek(0)
    tokens_gen = transform_tokens(tokenize.tokenize(stream.readline))
    return tokenize.untokenize(tokens_gen).decode(encoding)


# === AST modification.


class LateBoundDefaultTransformer(ast.NodeTransformer):
    @staticmethod
    def _is_marker_node(potential_node: object) -> TypeGuard[ast.Call]:
        return (
            isinstance(potential_node, ast.Call)
            and isinstance(potential_node.func, ast.Name)
            and potential_node.func.id == "_DEFER_MARKER"
        )

    @staticmethod
    def _replace_marker_node(node: ast.Call, index: int, all_previous_args: list[ast.arg]) -> ast.Call:
        lambda_arg_names = [arg.arg for arg in all_previous_args[:index]]
        new_lambda = ast.Lambda(
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(arg=name) for name in lambda_arg_names],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=ast.Tuple(elts=node.args) if len(node.args) > 1 else node.args[0],
        )
        return ast.Call(func=ast.Name(id="@defer", ctx=ast.Load()), args=[new_lambda], keywords=[])

    def _replace_late_bound_markers(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Replace the markers in the function defaults with actual defer objects.
        all_func_defaults = node.args.defaults + node.args.kw_defaults
        try:
            next(default for default in all_func_defaults if default is not None and self._is_marker_node(default))
        except StopIteration:
            return

        # Handle args that are allowed to be passed in positionally.
        positional_args = node.args.posonlyargs + node.args.args
        default_offset = len(positional_args) - len(node.args.defaults)

        markers_in_defaults = [
            (index, default) for index, default in enumerate(node.args.defaults) if self._is_marker_node(default)
        ]
        for index, marker in markers_in_defaults:
            actual_index = index + default_offset
            node.args.defaults[index] = self._replace_marker_node(marker, actual_index, positional_args)

        # Handle args that are keyword-only.
        all_args = positional_args + node.args.kwonlyargs
        kw_default_offset = len(positional_args)

        markers_in_kw_defaults = [
            (index, kw_default)
            for index, kw_default in enumerate(node.args.kw_defaults)
            if self._is_marker_node(kw_default)
        ]

        for index, marker in markers_in_kw_defaults:
            actual_index = index + kw_default_offset
            node.args.kw_defaults[index] = self._replace_marker_node(marker, actual_index, all_args)

    def _add_late_binding_evaluate_call(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Put a call to evaluate the defer objects, the late bindings, as the first line of the function.
        evaluate_expr = ast.Expr(
            value=ast.Call(
                func=ast.Name(id="@evaluate_late_binding", ctx=ast.Load()),
                args=[ast.Call(func=ast.Name(id="locals", ctx=ast.Load()), args=[], keywords=[])],
                keywords=[],
            )
        )

        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body.insert(1, evaluate_expr)
        else:
            node.body.insert(0, evaluate_expr)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self._replace_late_bound_markers(node)
        self._add_late_binding_evaluate_call(node)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self._replace_late_bound_markers(node)
        self._add_late_binding_evaluate_call(node)
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> ast.AST:
        """Import the defer type and evaluation functions so that the late binding-related symbols are valid."""

        expect_docstring = True
        position = 0
        for sub_node in node.body:
            if (
                expect_docstring
                and isinstance(sub_node, ast.Expr)
                and isinstance(sub_node.value, ast.Constant)
                and isinstance(sub_node.value.value, str)
            ):
                expect_docstring = False
            elif isinstance(sub_node, ast.ImportFrom) and sub_node.module == "__future__" and sub_node.level == 0:
                pass
            else:
                break

            position += 1

        aliases = [ast.alias("_defer", "@defer"), ast.alias("_evaluate_late_binding", "@evaluate_late_binding")]
        imports = ast.ImportFrom(module="__experimental__._features.late_bound_arg_defaults", names=aliases, level=0)
        node.body.insert(position, imports)

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    return ast.fix_missing_locations(LateBoundDefaultTransformer().visit(tree))


# Some of the parameter annotations are too narrow or wide, but they should be "overriden" by this decorator.
@copy_annotations(ast.parse)  # type: ignore
def parse(
    source: Union[str, ReadableBuffer],
    filename: str = "<unknown>",
    mode: str = "exec",
    *,
    type_comments: bool = False,
    feature_version: Optional[Tuple[int, int]] = None,
) -> ast.Module:
    return transform_ast(
        ast.parse(
            transform_source(source),
            filename,
            mode,
            type_comments=type_comments,
            feature_version=feature_version,
        )
    )