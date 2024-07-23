"""An implementation of late-bound function argument defaults (PEP 671) in pure Python."""

import ast
import tokenize
from io import BytesIO
from itertools import starmap
from typing import TypeGuard

from __experimental__._ast_helpers import find_import_spot
from __experimental__._core import _ExperimentalFeature, _Transformers
from __experimental__._misc import copy_annotations
from __experimental__._token_helpers import offset_line_horizontal, reverse_enumerate
from __experimental__._typing_compat import Buffer as ReadableBuffer


_MARKER = "_DEFER_MARKER"


class DeferredExpr:
    __slots__ = ("expr",)

    def __init__(self, expr: str, /) -> None:
        self.expr = expr

    def __repr__(self, /) -> str:
        return f"{type(self).__name__}({self.expr!r})"


def transform_tokens(tokens: list[tokenize.TokenInfo]) -> list[tokenize.TokenInfo]:
    """Replace `=>` with `= _DEFER_MARKER` in the token stream."""

    for i, tok in reverse_enumerate(tokens):
        if tok.exact_type == tokenize.GREATER and i > 0:
            peek_tok = tokens[i - 1]

            # "=>" should be connected with no space in between.
            if peek_tok.exact_type == tokenize.EQUAL and peek_tok.end == tok.start:
                # Fix the positions of the rest of the tokens on the same line.
                offset_line_horizontal(tokens, len(_MARKER), start_index=i + 1, line=tok.start[0])

                # Replace the current ">" token with the marker, i.e. "=>" becomes "= _DEFER_MARKER".
                new_start = (tok.start[0], tok.start[1] + 1)
                new_end = (new_start[0], new_start[1] + len(_MARKER) + 1)
                tokens[i] = tok._replace(type=tokenize.NAME, string=_MARKER, start=new_start, end=new_end)

    return tokens


def transform_source(source: str | ReadableBuffer) -> str:
    """Replaces late binding tokens with valid syntax, with explicit markers for the AST transformer."""

    if isinstance(source, str):
        source = source.encode("utf-8")
    stream = BytesIO(source)
    encoding, _ = tokenize.detect_encoding(stream.readline)
    stream.seek(0)
    tokens_list = transform_tokens(list(tokenize.tokenize(stream.readline)))
    return tokenize.untokenize(tokens_list).decode(encoding)


class LateBoundDefaultTransformer(ast.NodeTransformer):
    """An AST transformer that alters functions with defer markers to use the sentinel idiom for late binding.

    Notes
    -----
    The defer markers will be replaced with `DeferredExpr` objects that contain a string form of the expression.
    Meanwhile, the actual expressions will be put in the functions and assigned to the relevant variables, guarded by
    if conditions checking that the type of the given value is `DeferredExpr`.

    An example of the conversion::

        # Before
        def example(a: list[int], b: int = _DEFER_MARKER(len(a))):
            return [*a, b]

        # After
        def example(a: list[int], b: int = @DeferredExpr("len(a)")):
            if type(b) is @DeferredExpr:
                b = len(a)
            return [*a, b]

    "@" is used in the type name to avoid clobbering any user variables.
    """

    @staticmethod
    def _is_marker_node(potential_node: object) -> TypeGuard[ast.Call]:
        return (
            isinstance(potential_node, ast.Call)
            and isinstance(potential_node.func, ast.Name)
            and potential_node.func.id == "_DEFER_MARKER"
        )

    @staticmethod
    def _replace_marker_node(node: ast.Call, expr: ast.expr) -> ast.Call:
        node.func = ast.Name("@DeferredExpr", ast.Load())
        node.args = [ast.Constant(ast.unparse(expr))]
        return node

    @staticmethod
    def _create_conditional_default(name: str, default: ast.expr) -> ast.If:
        return ast.If(
            test=ast.Compare(
                left=ast.Call(func=ast.Name("type", ast.Load()), args=[ast.Name(name, ast.Load())], keywords=[]),
                ops=[ast.Is()],
                comparators=[ast.Name("@DeferredExpr", ast.Load())],
            ),
            body=[ast.Assign(targets=[ast.Name(name, ast.Store())], value=default)],
            orelse=[],
        )

    @classmethod
    def _replace_late_bound_markers(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        set_default_statements: list[tuple[str, ast.expr]] = []

        # Handle defaults for arguments that can be passed in positionally.
        positional_args = node.args.posonlyargs + node.args.args
        defaults_offset = len(positional_args) - len(node.args.defaults)

        for index, default in enumerate(node.args.defaults):
            if cls._is_marker_node(default):
                arg_index = index + defaults_offset
                temp_expr = ast.Tuple(elts=default.args) if len(default.args) > 1 else default.args[0]
                set_default_statements.append((positional_args[arg_index].arg, temp_expr))
                node.args.defaults[index] = cls._replace_marker_node(default, temp_expr)

        # Handle defaults for keyword-only arguments.
        for index, kw_default in enumerate(node.args.kw_defaults):
            if cls._is_marker_node(kw_default):
                temp_expr = ast.Tuple(elts=kw_default.args) if len(kw_default.args) > 1 else kw_default.args[0]
                set_default_statements.append((node.args.kwonlyargs[index].arg, temp_expr))
                node.args.kw_defaults[index] = cls._replace_marker_node(kw_default, temp_expr)

        if set_default_statements:
            # Add the conditionals for assigning the defaults in the function body, after a docstring if it exists.
            match node.body:
                case [ast.Expr(value=ast.Constant(value=str())), *_]:
                    insert_index = 1
                case _:
                    insert_index = 0

            node.body[insert_index:insert_index] = starmap(cls._create_conditional_default, set_default_statements)

    def _visit_Func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        self._replace_late_bound_markers(node)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._visit_Func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._visit_Func(node)

    def visit_Module(self, node: ast.Module) -> ast.AST:
        """Import the defer type and evaluation function so that the late binding-related symbols are valid."""

        import_position = find_import_spot(node, after_modules={"__future__"})

        aliases = [ast.alias("DeferredExpr", "@DeferredExpr")]
        imports = ast.ImportFrom(module="__experimental__._features.late_bound_arg_defaults", names=aliases, level=0)
        node.body.insert(import_position, imports)

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    """Walk through an AST to turn the `_DEFER_MARKER(...)` expressions into `DeferredExpr` instantiations,
    move the late-bound default expressions into their functions, and finally import `DeferredExpr`.
    """

    return ast.fix_missing_locations(LateBoundDefaultTransformer().visit(tree))


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
    """Convert source code with late-bound function argument defaults to a valid AST.

    Notes
    -----
    The runtime annotations for this method are a bit off; see `ast.parse`, the function this wraps, for details about
    the actual signature.
    """

    return transform_ast(
        ast.parse(
            transform_source(source),
            filename,
            mode,
            type_comments=type_comments,
            feature_version=feature_version,
        )
    )


FEATURE = _ExperimentalFeature(
    "late_bound_arg_defaults",
    "2024.03.30",
    transformers=_Transformers(transform_source, transform_tokens, transform_ast, parse),
    reference="https://peps.python.org/pep-0671/",
)
