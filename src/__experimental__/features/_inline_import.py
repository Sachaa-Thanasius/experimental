import ast
import tokenize
from collections.abc import Iterable
from io import StringIO

__all__ = ("transform_source", "transform_ast", "parse")


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
            old_row = end_paren_token.start[0]

            for ltr_tok in tokens_iter:
                if old_row != int(ltr_tok.start[0]):
                    new_tokens.append(ltr_tok)
                    break

                new_start = (ltr_tok.start[0], ltr_tok.start[1] + 18)
                new_end = (ltr_tok.end[0], ltr_tok.end[1] + 18)
                new_tokens.append(ltr_tok._replace(start=new_start, end=new_end))
        else:
            new_tokens.append(tok)

    return new_tokens


def transform_source(src: str) -> str:
    tokens_list = transform_tokens(tokenize.generate_tokens(StringIO(src).readline))
    return tokenize.untokenize(tokens_list)


# === AST modification.


class ImportExpressionTransformer(ast.NodeTransformer):
    @classmethod
    def _collapse_attributes(cls, node: ast.Attribute | ast.Name) -> str:
        if isinstance(node, ast.Name):
            return node.id

        if not (
            isinstance(node, ast.Attribute)  # pyright: ignore[reportUnnecessaryIsInstance]
            and isinstance(node.value, (ast.Attribute, ast.Name))  # noqa: UP038
        ):
            msg = "Only names and attributes can be within the inline import expression."
            raise SyntaxError(msg)  # noqa: TRY004

        return cls._collapse_attributes(node.value) + f".{node.attr}"

    def visit_Call(self, node: ast.Call) -> ast.AST:
        match node:
            case ast.Call(func=ast.Name(id="_IMPORTLIB_MARKER"), args=[ast.Attribute() | ast.Name() as import_arg]):
                node.func = ast.Attribute(
                    value=ast.Name(id="importlib", ctx=ast.Load()),
                    attr="import_module",
                    ctx=ast.Load(),
                )
                node.args[0] = ast.Constant(value=self._collapse_attributes(import_arg))
            case _:
                pass
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> ast.AST:
        expect_docstring = True
        position = 0
        for sub_node in node.body:
            match sub_node:
                case ast.Expr(value=ast.Constant(value=str())) if expect_docstring:
                    expect_docstring = False
                case ast.ImportFrom(module="__future__", level=0):
                    pass
                case _:
                    break
            position += 1

        import_node = ast.Import(names=[ast.alias("importlib")])
        node.body.insert(position, import_node)

        return self.generic_visit(node)


def transform_ast(tree: ast.AST) -> ast.Module:
    return ast.fix_missing_locations(ImportExpressionTransformer().visit(tree))


def parse(code: str) -> ast.Module:
    return transform_ast(ast.parse(transform_source(code)))
