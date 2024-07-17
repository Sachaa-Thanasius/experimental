"""An implementation of inline import expressions in pure Python."""

import ast
import tokenize
from io import BytesIO

from __experimental__._ast_helpers import collapse_plain_attribute_or_name
from __experimental__._core import _ExperimentalFeature, _Transformers
from __experimental__._misc import copy_annotations
from __experimental__._token_helpers import offset_line_horizontal, offset_token_horizontal
from __experimental__._typing_compat import ReadableBuffer


_MARKER = "_IMPORTLIB_MARKER"


def transform_tokens(tokens: list[tokenize.TokenInfo]) -> list[tokenize.TokenInfo]:
    """Find the inline import expressions in a list of tokens and replace the relevant tokens to wrap the imported
    modules with `_IMPORTLIB_MARKER(...)`.

    Later, the AST transformer step will replace those with valid import expressions.
    """

    for i in reversed(range(len(tokens))):
        tok = tokens[i]
        # "!" is only an OP in >=3.12.
        if tok.type in {tokenize.OP, tokenize.ERRORTOKEN} and tok.string == "!":
            # Collect all name and attribute access-related tokens directly connected to the "!".
            has_invalid_syntax = False
            looking_for_name = True

            temp_i = i - 1
            for temp_i in reversed(range(i)):
                temp_tok = tokens[temp_i]
                if temp_tok.exact_type != (tokenize.NAME if looking_for_name else tokenize.DOT):
                    # Check if the "!" was placed somewhere in a class definition statement, e.g. "class Fo!o: pass".
                    has_invalid_syntax = (temp_tok.exact_type == tokenize.NAME) and (temp_tok.string == "class")

                    # There's a name immediately following "!". Might be a f-string conversion flag
                    # like "f'{thing!r}'" or just something invalid like "def fo!o(): pass".
                    if i < (len(tokens) - 1):
                        peek_tok = tokens[i + 1]
                        has_invalid_syntax = has_invalid_syntax or peek_tok.type == tokenize.NAME

                    break

                looking_for_name = not looking_for_name

            if has_invalid_syntax or (temp_i == (i - 1)):
                # The "!" is by itself or in a bad spot. Let it error later if it's wrong.
                # Erroring early would prevent other token transformers from potentially fixing the issue.
                continue

            # The start of the inline import expression.
            marker_start_border = temp_i + 1

            # Replace the end of the inline import expression, the current token, "!", with a closing parenthesis.
            tokens[i] = tok._replace(type=tokenize.OP, string=")")

            # Insert a call with the MARKER name just before the inline import expression.
            imp_expr_first = tokens[marker_start_border]
            ief_row, ief_col = imp_expr_first.start

            marker_tok = imp_expr_first._replace(
                type=tokenize.NAME, string=_MARKER, end=(ief_row, ief_col + len(_MARKER))
            )
            open_paren_tok = offset_token_horizontal(
                tokenize.TokenInfo(tokenize.OP, "(", (ief_row, ief_col), (ief_row, ief_col + 1), imp_expr_first.line),
                len(_MARKER),
            )
            tokens[marker_start_border:marker_start_border] = (marker_tok, open_paren_tok)

            # Adjust the positions of the tokens after the just inserted marker and parenthesis.
            offset_line_horizontal(tokens, len(_MARKER) + 1, start_index=marker_start_border + 2, line=ief_row)

    return tokens


def transform_source(source: str | ReadableBuffer) -> str:
    """Replace and wrap inline import expressions in source code so that it has valid syntax, with explicit markers for
    where to perform the imports.
    """

    if isinstance(source, str):
        source = source.encode("utf-8")
    stream = BytesIO(source)
    encoding, _ = tokenize.detect_encoding(stream.readline)
    stream.seek(0)
    tokens_list = transform_tokens(list(tokenize.tokenize(stream.readline)))
    return tokenize.untokenize(tokens_list).decode(encoding)


class InlineImportTransformer(ast.NodeTransformer):
    """An AST transformer that replaces `_IMPORTLIB_MARKER(...)` with `__import__("importlib").import_module(...)`."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Replace the _IMPORTLIB_MARKER calls with a valid inline import expression."""

        match node:
            case ast.Call(func=ast.Name("_IMPORTLIB_MARKER"), args=[(ast.Attribute() | ast.Name()) as arg]):
                node.func = ast.Attribute(
                    value=ast.Call(
                        func=ast.Name("__import__", ctx=ast.Load()),
                        args=[ast.Constant(value="importlib")],
                        keywords=[],
                    ),
                    attr="import_module",
                    ctx=arg.ctx,
                )

                try:
                    identifier = collapse_plain_attribute_or_name(arg)
                except TypeError:
                    msg = "Only names and attribute access (dot operator) can be within the inline import expression."
                    raise SyntaxError(msg) from None
                else:
                    node.args[0] = ast.Constant(value=identifier)

            case _:
                pass

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    """Walk through an AST and fix it to turn the `_IMPORTLIB_MARKER(...)` expressions into valid import statements."""

    return ast.fix_missing_locations(InlineImportTransformer().visit(tree))


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
    """Convert source code with inline import expressions to a valid AST.

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
    "inline_import",
    "2024.04.04",
    transformers=_Transformers(transform_source, transform_tokens, transform_ast, parse),
    reference="https://github.com/ioistired/import-expression-parser",
)
