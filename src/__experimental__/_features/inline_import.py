"""An implementation of inline import expressions in pure Python."""

import ast
import tokenize
from collections.abc import Iterable
from io import BytesIO

from __experimental__._ast_helpers import collapse_plain_attribute_or_name
from __experimental__._core import _ExperimentalFeature, _Transformers
from __experimental__._misc import copy_annotations
from __experimental__._peekable import Peekable
from __experimental__._token_helpers import offset_line_horizontal, offset_token_horizontal
from __experimental__._typing_compat import ReadableBuffer, override


__all__ = ("transform_tokens", "transform_source", "transform_ast", "parse", "FEATURE")


def transform_tokens(tokens: Iterable[tokenize.TokenInfo]) -> list[tokenize.TokenInfo]:
    """Find the inline import expressions in a list of tokens and replace the relevant tokens to wrap the imported
    modules with `_IMPORTLIB_MARKER(...)`.

    Later, the AST transformer step will replace those with valid import expressions.
    """

    # TODO: Somehow make this a generator and/or make signature consistent with other transform_tokens predicates.
    new_tokens: list[tokenize.TokenInfo] = []

    peekable_tokens_iter = Peekable(tokens)
    for tok in peekable_tokens_iter:
        # "!" is only an OP in >=3.12.
        if tok.type in {tokenize.OP, tokenize.ERRORTOKEN} and tok.string == "!":
            has_invalid_syntax = False

            # Collect all name and attribute access-related tokens directly connected to the "!".
            last_place = len(new_tokens)
            looking_for_name = True

            for old_tok in reversed(new_tokens):
                # TODO: Determine if this needs to be even stricter.
                if old_tok.exact_type != (tokenize.NAME if looking_for_name else tokenize.DOT):
                    has_invalid_syntax = (
                        # The "!" was placed somewhere in a class definition, e.g. "class Fo!o: pass".
                        (old_tok.exact_type == tokenize.NAME and old_tok.string == "class")
                        # There's a name immediately following "!". Might be a f-string conversion flag
                        # like "f'{thing!r}'" or just something invalid like "def fo!o(): pass".
                        or (peekable_tokens_iter.has_more() and (peekable_tokens_iter.peek().type == tokenize.NAME))
                    )
                    break
                last_place -= 1
                looking_for_name = not looking_for_name

            # The "!" is just by itself or in a bad spot. Let it error later if it's wrong.
            # Also allows other token transformers to work with it without erroring early.
            if has_invalid_syntax or last_place == len(new_tokens):
                new_tokens.append(tok)
                continue

            # Insert "_IMPORTLIB_MARKER(" just before the inline import expression.
            old_first = new_tokens[last_place]
            old_f_row, old_f_col = old_first.start

            new_tokens[last_place:last_place] = [
                old_first._replace(type=tokenize.NAME, string="_IMPORTLIB_MARKER", end=(old_f_row, old_f_col + 17)),
                tokenize.TokenInfo(
                    tokenize.OP,
                    "(",
                    (old_f_row, old_f_col + 17),
                    (old_f_row, old_f_col + 18),
                    old_first.line,
                ),
            ]

            # Adjust the positions of the following tokens within the inline import expression.
            new_tokens[last_place + 2 :] = (offset_token_horizontal(tok, 18) for tok in new_tokens[last_place + 2 :])

            # Add a closing parenthesis.
            (end_row, end_col) = new_tokens[-1].end
            line = new_tokens[-1].line
            end_paren_token = tokenize.TokenInfo(tokenize.OP, ")", (end_row, end_col), (end_row, end_col + 1), line)
            new_tokens.append(end_paren_token)

            # Fix the positions of the rest of the tokens on the same line.
            fixed_line_tokens: list[tokenize.TokenInfo] = []
            after_tok: tokenize.TokenInfo | None = None

            curr_row = end_paren_token.start[0]

            fixed_line_tokens.extend(offset_line_horizontal(peekable_tokens_iter, curr_row, 18))
            if fixed_line_tokens[-1].start[0] != curr_row:
                after_tok = fixed_line_tokens.pop()

            # Check the rest of the line for inline import expressions.
            new_tokens.extend(transform_tokens(fixed_line_tokens))

            if after_tok:
                new_tokens.append(after_tok)
        else:
            new_tokens.append(tok)

    return new_tokens


def transform_source(source: str | ReadableBuffer) -> str:
    """Replace and wrap inline import expressions in source code so that it has valid syntax, with explicit markers for
    where to perform the imports.
    """

    if isinstance(source, str):
        source = source.encode("utf-8")
    stream = BytesIO(source)
    encoding, _ = tokenize.detect_encoding(stream.readline)
    stream.seek(0)
    tokens_list = transform_tokens(tokenize.tokenize(stream.readline))
    return tokenize.untokenize(tokens_list).decode(encoding)


class InlineImportTransformer(ast.NodeTransformer):
    """An AST transformer that replaces `_IMPORTLIB_MARKER(...)` with `__import__("importlib").import_module(...)`."""

    @override
    def visit_Call(self, node: ast.Call) -> ast.AST:
        """Replace the _IMPORTLIB_MARKER calls with a valid inline import expression."""

        match node:
            case ast.Call(func=ast.Name(id="_IMPORTLIB_MARKER"), args=[(ast.Attribute() | ast.Name()) as arg]):
                node.func = ast.Attribute(
                    value=ast.Call(
                        func=ast.Name(id="__import__", ctx=ast.Load()),
                        args=[ast.Constant(value="importlib")],
                        keywords=[],
                    ),
                    attr="import_module",
                    ctx=ast.Load(),
                )

                try:
                    node.args[0] = ast.Constant(value=collapse_plain_attribute_or_name(arg))
                except TypeError:
                    msg = "Only names and attribute access (dot operator) can be within the inline import expression."
                    raise SyntaxError(msg) from None

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
    The runtime annotations for this method are a bit off; see `ast.parse`, the function this wraps, for details about the
    actual signature.
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
