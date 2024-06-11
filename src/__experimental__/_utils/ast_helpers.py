import ast
from collections import deque
from typing import Any

__all__ = ("collapse_plain_attribute_or_name", "compare_asts")


def collapse_plain_attribute_or_name(node: ast.Attribute | ast.Name) -> str:
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


def compare_asts(first_node: ast.AST | list[ast.AST] | Any, second_node: ast.AST | list[ast.AST] | Any) -> bool:
    """Compare two AST nodes for equality, to see if they have the same field structure with the same values.

    This only takes into account fields present in a node's _fields list (excluding "ctx").

    Notes
    -----
    The algorithm is modified from https://stackoverflow.com/a/19598419 to be iterative instead of recursive.
    """

    nodes = deque([(first_node, second_node)])

    while nodes:
        node1, node2 = nodes.pop()

        if type(node1) is not type(node2):
            return False

        if isinstance(node1, ast.AST):
            nodes.extend((getattr(node1, field), getattr(node2, field)) for field in node1._fields if field != "ctx")
            continue

        if isinstance(node1, list):
            assert isinstance(node2, list)
            try:
                nodes.extend(zip(node1, node2, strict=True))
            except ValueError:
                return False

            continue

        if node1 != node2:
            return False

    return True
