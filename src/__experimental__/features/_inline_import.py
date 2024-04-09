from __future__ import annotations

import ast
import tokenize
from collections.abc import Iterable
from io import BytesIO
from typing import TYPE_CHECKING, Optional, Tuple, Union

from __experimental__._utils import copy_annotations

if TYPE_CHECKING:
    from typing_extensions import Buffer as ReadableBuffer

__all__ = ("transform_tokens", "transform_source", "transform_ast", "parse")


# === Token modification.


def transform_tokens(tokens: Iterable[tokenize.TokenInfo]) -> list[tokenize.TokenInfo]:
    new_tokens: list[tokenize.TokenInfo] = []

    tokens_iter = iter(tokens)
    for tok in tokens_iter:
        # ! is only an OP in 3.12+.
        if tok.type in {tokenize.OP, tokenize.ERRORTOKEN} and tok.string == "!":
            last_place = len(new_tokens)

            # Collect all name and attribute access-related tokens directly connected to the !.
            for old_tok in reversed(new_tokens):
                if old_tok.exact_type not in {tokenize.DOT, tokenize.NAME}:
                    break
                last_place -= 1

            # The question mark is just by itself. Let it error at the AST stage if it's wrong.
            if last_place == len(new_tokens):
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
            for i, old_tok in enumerate(new_tokens[last_place + 2 :], start=last_place + 2):
                (start_row, start_col), (end_row, end_col) = old_tok.start, old_tok.end
                new_tokens[i] = old_tok._replace(start=(start_row, start_col + 18), end=(end_row, end_col + 18))

            # Add a closing parenthesis.
            (end_row, end_col) = new_tokens[-1].end
            line = new_tokens[-1].line
            end_paren_token = tokenize.TokenInfo(tokenize.OP, ")", (end_row, end_col), (end_row, end_col + 1), line)
            new_tokens.append(end_paren_token)

            # Fix the positions of the rest of the tokens on the same line.
            fixed_tokens: list[tokenize.TokenInfo] = []
            after_tok: tokenize.TokenInfo | None = None

            old_row = end_paren_token.start[0]

            for ltr_tok in tokens_iter:
                if old_row != int(ltr_tok.start[0]):
                    after_tok = ltr_tok
                    break

                new_start = (ltr_tok.start[0], ltr_tok.start[1] + 18)
                new_end = (ltr_tok.end[0], ltr_tok.end[1] + 18)
                fixed_tokens.append(ltr_tok._replace(start=new_start, end=new_end))

            new_tokens.extend(transform_tokens(fixed_tokens))

            if after_tok:
                new_tokens.append(after_tok)
        else:
            new_tokens.append(tok)

    return new_tokens


def transform_source(source: Union[str, ReadableBuffer]) -> str:
    if isinstance(source, str):
        source = source.encode("utf-8")
    stream = BytesIO(source)
    encoding, _ = tokenize.detect_encoding(stream.readline)
    stream.seek(0)
    tokens_list = transform_tokens(tokenize.tokenize(stream.readline))
    return tokenize.untokenize(tokens_list).decode(encoding)


# === AST modification.


class ImportExpressionTransformer(ast.NodeTransformer):
    @classmethod
    def _collapse_attributes(cls, node: ast.Attribute | ast.Name) -> str:
        if isinstance(node, ast.Name):
            return node.id

        if not (
            isinstance(node, ast.Attribute)  # pyright: ignore[reportUnnecessaryIsInstance]
            and isinstance(node.value, (ast.Attribute, ast.Name))
        ):
            msg = "Only names and attributes can be within the inline import expression."
            raise SyntaxError(msg)  # noqa: TRY004

        return cls._collapse_attributes(node.value) + f".{node.attr}"

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "_IMPORTLIB_MARKER"
            and len(node.args) == 1
            and isinstance(node.args[0], (ast.Attribute, ast.Name))
        ):
            import_arg = node.args[0]
            node.func = ast.Attribute(
                value=ast.Call(
                    func=ast.Name(id="__import__", ctx=ast.Load()),
                    args=[ast.Constant(value="importlib")],
                    keywords=[],
                ),
                attr="import_module",
                ctx=ast.Load(),
            )
            node.args[0] = ast.Constant(value=self._collapse_attributes(import_arg))

        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> ast.AST:
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

        import_node = ast.Import(names=[ast.alias("importlib")])
        node.body.insert(position, import_node)

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    return ast.fix_missing_locations(ImportExpressionTransformer().visit(tree))


# Some of the parameter annotations are wrong, but they should be "overriden" by this decorator.
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
