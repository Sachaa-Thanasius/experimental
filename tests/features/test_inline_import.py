import ipaddress
import urllib.parse
from typing import TYPE_CHECKING, Annotated

import pytest
from __experimental__._features import inline_import


@pytest.mark.parametrize(
    ("test_source", "expected_result"),
    [
        (
            "collections!.Counter(urllib.parse!.quote('foo'))",
            "_IMPORTLIB_MARKER(collections).Counter(_IMPORTLIB_MARKER(urllib.parse).quote('foo'))",
        ),
        ("ipaddress!.IPV6LENGTH", "_IMPORTLIB_MARKER(ipaddress).IPV6LENGTH"),
        ("urllib.parse!.quote('?')", "_IMPORTLIB_MARKER(urllib.parse).quote('?')"),
    ],
)
def test_transform_source(test_source: str, expected_result: str):
    retokenized_source = inline_import.transform_source(test_source)
    assert retokenized_source == expected_result


@pytest.mark.parametrize(
    ("test_source", "expected_result"),
    [
        ("collections!.Counter(urllib.parse!.quote('foo'))", {"f": 1, "o": 2}),
        ("ipaddress!.IPV6LENGTH", ipaddress.IPV6LENGTH),
        ("urllib.parse!.quote('?')", urllib.parse.quote("?")),
    ],
)
def test_parse(test_source: str, expected_result: object):
    tree = inline_import.parse(test_source, mode="eval")
    code = compile(tree, "<string>", "eval")
    result = eval(code)

    assert result == expected_result


@pytest.mark.parametrize(
    ("test_fstring", "expected_result"),
    [
        ("f'{value!r}'", "'Here I am'"),
        ("f'{value!r:20}'", "'Here I am'         "),
        ("f'{value=!r}'", "value='Here I am'"),
        ("f'{value = !r}'", "value = 'Here I am'"),
        ("f'{value=!r:20}'", "value='Here I am'         "),
        ("f'{value = !r:20}'", "value = 'Here I am'         "),
    ],
)
def test_regular_fstring(test_fstring: str, expected_result: object):
    globals_ = {"value": "Here I am"}

    tree = inline_import.parse(test_fstring, mode="eval")
    code = compile(tree, "<string>", "eval")
    result = eval(code, globals_)

    assert result == expected_result


@pytest.mark.parametrize(
    "invalid_expr",
    [
        "!a",
        "a.!b",
        "!a.b",
        "a!.b!",
        "a.b!.c!",
        "a!.b!.c",
        "a.b.!c",
        "a.!b.c",
        "a.!b.!c" "!a.b.c",
        "!a.b.!c",
        "!a.!b.c",
        "!a.!b.!c" "a!b",
        "ab.bc.d!e",
        "ab.b!c",
    ],
)
def test_invalid_attribute_syntax(invalid_expr: str):
    with pytest.raises(SyntaxError):
        _ = inline_import.parse(invalid_expr)


def test_import_op_as_attr_name():
    with pytest.raises(SyntaxError):
        _ = inline_import.parse("a.!.b")


@pytest.mark.parametrize("test_source", ["del a!.b", "a!.b = 1", "del a.b.c!.d", "a.b.c!.d = 1"])
def test_del_store_import(test_source: str):
    tree = inline_import.parse(test_source)
    _ = compile(tree, "<string>", "exec")


@pytest.mark.parametrize("test_source", ["del a!", "a! = 1", "del a.b!", "a.b! = 1"])
def test_invalid_del_store_import(test_source: str):
    # TODO: Change test so it doesn't hide why test_del_store_import might fail.

    with pytest.raises(
        (
            ValueError,  # raised by builtins.compile
            SyntaxError,  # raised by inline_import.parse
        )
    ):
        _ = inline_import.parse(test_source)


def test_lone_import_op():
    with pytest.raises(SyntaxError):
        _ = inline_import.parse("!")


@pytest.mark.parametrize(
    "invalid_source",
    [
        "def foo(x!): pass",
        "def foo(*x!): pass",
        "def foo(**y!): pass",
        "def foo(*, z!): pass",
        # note space around equals sign:
        # class Y(Z!=1) is valid if Z.__ne__ returns a class
        "class Y(Z! = 1): pass",
    ],
)
def test_invalid_argument_syntax(invalid_source: str):
    with pytest.raises(SyntaxError):
        _ = inline_import.parse(invalid_source)


@pytest.mark.parametrize(
    "invalid_source",
    [
        "def !foo(y): pass",
        "def fo!o(y): pass",
        "def foo!(y): pass",
        "class X!: pass",
        "class Fo!o: pass",
        "class !Foo: pass",
        # note space around equals sign:
        # class Y(Z!=1) is valid if Z.__ne__ returns a class
        "class Y(Z! = 1): pass",
    ],
)
def test_invalid_def_syntax(invalid_source: str):
    with pytest.raises(SyntaxError):
        _ = inline_import.parse(invalid_source, "<string>")


def test_kwargs():
    import collections

    tree = inline_import.parse("dict(x=collections!)", mode="eval")
    code = compile(tree, "<string>", "eval")
    x = eval(code)["x"]

    assert x is collections


@pytest.mark.parametrize(
    ("test_source", "annotation_var"),
    [
        ("def test_func() -> typing!.Annotated: pass", "return"),
        ("def test_func(x: typing!.Annotated): pass", "x"),
        ("def test_func(x: typing!.Annotated = 1): pass", "x"),
    ],
)
def test_typehint_conversion(test_source: str, annotation_var: str):
    globals_: dict[str, object] = {}

    tree = inline_import.parse(test_source)
    code = compile(tree, "<string>", "exec")
    exec(code, globals_)

    test_func = globals_["test_func"]

    assert test_func.__annotations__[annotation_var] is Annotated


@pytest.mark.parametrize(
    "invalid_source",
    [
        "import x!",
        "import x.y!",
        "import x!.y!",
        "from x!.y import z",
        "from x.y import z!",
        "from w.x import y as z!",
        "from w.x import y as z, a as b!",
    ],
)
def test_import_statement(invalid_source: str):
    with pytest.raises(SyntaxError):
        _ = inline_import.parse(invalid_source, mode="exec")


def test_importer_name_not_mangled():
    # If the import marker starts with '__', this will fail due to name mangling.
    _ = inline_import.parse("class Foo: x = io!")


def test_bytes_input():
    tree = inline_import.parse(b"typing!.TYPE_CHECKING", mode="eval")
    code = compile(tree, "<string>", "eval")
    assert eval(code) == TYPE_CHECKING
