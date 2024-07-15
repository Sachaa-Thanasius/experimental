import ast

from __experimental__._features import elide_cast


TEST_INPUT = """\
from typing import cast as mycast

import typing_extensions as tpe

from typing_extensions import cast as tpecast


class Class:
    thing = mycast(str, 1)

    def func(self, a: int) -> bool:
        return mycast(bool, a)

    def func2(self, c):
        c = tpe.cast(str, c)
        thing = tpecast(bool, c)
        return tpe.cast(str, c)

    def func3(self, d):
        import typing as tp
        return tp.cast(list, d)

    def func4(self, e):
        from unrelated import cast
        return cast(tuple, e)
"""

EXPECTED = """\
from typing import cast as mycast
import typing_extensions as tpe
from typing_extensions import cast as tpecast

class Class:
    thing = 1

    def func(self, a: int) -> bool:
        return a

    def func2(self, c):
        thing = c
        return c

    def func3(self, d):
        import typing as tp
        return d

    def func4(self, e):
        from unrelated import cast
        return cast(tuple, e)\
"""


def test_cast_tracking():
    expected = [
        ("typing.cast", "mycast", 9),
        ("typing.cast", "mycast", 12),
        ("typing_extensions.cast", "tpe.cast", 15),
        ("typing_extensions.cast", "tpecast", 16),
        ("typing_extensions.cast", "tpe.cast", 17),
        ("typing.cast", "tp.cast", 21),
    ]

    transformer = elide_cast.CastElisionTransformer()
    transformer.visit(ast.parse(TEST_INPUT))
    assert transformer.used_at == expected


def test_cast_eliding():
    tree = elide_cast.transform_ast(ast.parse(TEST_INPUT))
    assert ast.unparse(tree) == EXPECTED
