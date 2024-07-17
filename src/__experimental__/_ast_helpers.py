import ast
from collections import ChainMap, deque


__all__ = ("collapse_plain_attribute_or_name", "compare_asts", "find_import_spot", "ScopeTracker")


def collapse_plain_attribute_or_name(node: ast.Attribute | ast.Name, /) -> str:
    """Convert a attribute access (or name) AST node into a string representing how it would look as code.

    Raises
    ------
    TypeError
        If the node can't be reduced to a form like "a.b.c", i.e. it's more than chained attribute access or a name.

    Examples
    --------
    >>> import ast
    >>> node = ast.parse("a.b.c")
    >>> collapse_plain_attribute(node.body[0].value)
    "a.b.c"

    >>> node = ast.parse("a")
    >>> collapse_plain_attribute(node.body[0].value)
    "a"

    >>> node = ast.parse("a.b[0].c")
    >>> collapse_plain_attribute(node.body[0].value)
    TypeError: Only names and attribute access (dot operator) can be within this AST.
    """

    names: deque[str] = deque()

    while not isinstance(node, ast.Name):
        match node:
            case ast.Attribute(value=(ast.Attribute() | ast.Name()) as value):
                names.appendleft(node.attr)
                node = value
            case _:
                msg = "Only names and attribute access (dot operator) can be within this AST."
                raise TypeError(msg)

    names.appendleft(node.id)
    return ".".join(names)


def compare_asts(a: ast.AST | list[ast.AST], b: ast.AST | list[ast.AST], /, *, include_ctx: bool = False) -> bool:
    """Compare two ASTs or lists of ASTs to see if their fields match in structure and values.

    Parameters
    ----------
    a: ast.AST | list[ast.AST]
        The first AST.
    b: ast.AST | list[ast.AST]
        The second AST.
    include_ctx: bool, default=False
        Whether to take ASTs's `ctx` fields, should they be present, into account for the comparison.

    Notes
    -----
    The algorithm is modified from https://stackoverflow.com/a/19598419 to be iterative instead of recursive. Also,
    it only takes looks at fields present in a node's `_fields` attribute.
    """

    nodes = deque([(a, b)])

    while nodes:
        a, b = nodes.pop()

        if type(a) is not type(b):
            return False

        if isinstance(a, ast.AST):
            if include_ctx:
                nodes.extend((getattr(a, field), getattr(b, field)) for field in a._fields)
            else:
                nodes.extend((getattr(a, field), getattr(b, field)) for field in a._fields if field != "ctx")
            continue

        if isinstance(a, list):
            assert isinstance(b, list)
            try:
                nodes.extend(zip(a, b, strict=True))
            except ValueError:
                return False

            continue

        if a != b:
            return False

    return True


def find_import_spot(node: ast.Module, *, after_modules: set[str] | None = None) -> int:
    """Find the first index in an ast.Module's body that's after the module-level docstring (if it's present) and after
    the given top-level "from" imports.
    """

    if after_modules is None:
        after_modules = {"__future__", "__experimental__"}

    expect_docstring = True
    position = 0

    for sub_node in node.body:
        match sub_node:
            case ast.Expr(value=ast.Constant(value=str())) if expect_docstring:
                expect_docstring = False
            case ast.ImportFrom(module=mod_name, level=0) if mod_name in after_modules:
                pass
            case _:
                break

        position += 1

    return position


class ScopeTracker(ast.NodeTransformer):
    """An AST transformer that helps track Python scopes and what's in them. Subclasses should call super().method() if
    they override the visit_Lambda(), visitFunctionDef(), visit_AsyncFunctionDef(), or visitClassDef() methods.

    Attributes
    ----------
    scopes: ChainMap[str, str | None]
        A chain of mappings to use for tracking what's in various scopes. New mappings are automatically added when
        entering classes and functions and removed when leaving them.

    Notes
    -----
    Reference for tracking scopes within an AST: https://stackoverflow.com/a/55834093
    """

    def __init__(self) -> None:
        self.scopes: ChainMap[str, str | None] = ChainMap()

    def _visit_Block(self, node: ast.AST) -> ast.AST:
        self.scopes = self.scopes.new_child()
        mod_node = self.generic_visit(node)
        self.scopes = self.scopes.parents
        return mod_node

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        return self._visit_Block(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._visit_Block(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._visit_Block(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return self._visit_Block(node)
