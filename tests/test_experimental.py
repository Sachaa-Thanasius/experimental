import __future__

import ast
import importlib.util
import ipaddress
import sys
import time
import types
import typing
import urllib.parse

import pytest
from __experimental__ import install, lazy_module_import, uninstall
from __experimental__.features import _inline_import as inline_import, _late_bound_arg_defaults as late_bind

# FIXME: Make tests more comprehensive.


class TestLateBoundArgDefaults:
    original_source = """\
from typing import Dict, List

def test_func(
    z: float,
    a: int = 1,
    b: List[int] => ([a] * a),
    /,
    c: Dict[str, int] => ({str(a): b}),
    *,
    d: str => (str(a) + str(c)),
):
    return (z, a, b, c, d)
"""

    post_retokenize_source = """\
from typing import Dict, List

def test_func(
    z: float,
    a: int = 1,
    b: List[int] = _DEFER_MARKER([a] * a),
    /,
    c: Dict[str, int] = _DEFER_MARKER({str(a): b}),
    *,
    d: str = _DEFER_MARKER(str(a) + str(c)),
):
    return (z, a, b, c, d)
"""

    def test_late_binding_logic(self) -> None:
        def late_binding_logic_example(
            a: int,
            b: float = 1.0,
            /,
            ex: str = "hello",
            *,
            c: typing.List[object] = late_bind._defer(lambda a, b, ex: ["Preceding args", a, b, ex]),  # noqa: B008
            d: bool = False,
            e: int = late_bind._defer(lambda a, b, ex, c, d: len(c)),
        ) -> typing.Tuple[typing.List[object], int]:
            late_bind._evaluate_late_binding(locals())
            return c, e

        c, e = late_binding_logic_example(10)
        assert c == ["Preceding args", 10, 1.0, "hello"]
        assert e == 4

    def test_transform_source(self) -> None:
        retokenized_source = late_bind.transform_source(self.original_source)
        assert retokenized_source == self.post_retokenize_source

    def test_transform_ast(self) -> None:
        globals_: typing.Dict[str, typing.Any] = {}

        tree = late_bind.transform_ast(ast.parse(self.post_retokenize_source))
        code = compile(tree, "<string>", "exec")
        exec(code, globals_)

        test_func = globals_["test_func"]

        assert test_func.__defaults__[0] == 1
        assert isinstance(test_func.__defaults__[1], late_bind._defer)
        assert isinstance(test_func.__defaults__[2], late_bind._defer)

    def test_transform_ast_with_docstring(self) -> None:
        original_source = f'"""Module level docstring"""\n{self.post_retokenize_source}'
        globals_: typing.Dict[str, typing.Any] = {}

        tree = late_bind.transform_ast(ast.parse(original_source))
        code = compile(tree, "<string>", "exec")
        exec(code, globals_)

        module_doc = globals_["__doc__"]
        test_func = globals_["test_func"]

        assert module_doc == "Module level docstring"
        assert isinstance(test_func, types.FunctionType)

    def test_transform_ast_with_future_import(self) -> None:
        original_source = f"from __future__ import annotations\n{self.post_retokenize_source}"

        globals_: typing.Dict[str, typing.Any] = {}

        tree = late_bind.transform_ast(ast.parse(original_source))
        code = compile(tree, "<string>", "exec")
        exec(code, globals_)

        anns = globals_["annotations"]
        test_func = globals_["test_func"]

        assert anns == __future__.annotations
        assert isinstance(test_func, types.FunctionType)

    def test_transform_ast_with_docstring_and_future_import(self) -> None:
        original_source = (
            f'"""Module level docstring"""\nfrom __future__ import annotations\n{self.post_retokenize_source}'
        )

        globals_: typing.Dict[str, typing.Any] = {}

        tree = late_bind.transform_ast(ast.parse(original_source))
        code = compile(tree, "<string>", "exec")
        exec(code, globals_)

        module_doc = globals_["__doc__"]
        anns = globals_["annotations"]
        test_func = globals_["test_func"]

        assert module_doc == "Module level docstring"
        assert anns == __future__.annotations
        assert isinstance(test_func, types.FunctionType)

    def test_loader(self) -> None:
        install()
        from tests.sample_late_bound_arg import example_func

        uninstall()

        z, a, b, c, d = example_func(2.0, 3)
        assert z == 2.0
        assert a == 3
        assert b == [3, 3, 3]
        assert c == {"3": [3, 3, 3]}
        assert d == "2.0{'3': [3, 3, 3]}"


class TestInlineImport:
    """Many of these tests are modified from import_expression's own."""

    @pytest.mark.parametrize(
        "test_source, expected_result",
        [
            (
                "collections!.Counter(urllib.parse!.quote('foo'))",
                "_IMPORTLIB_MARKER(collections).Counter(_IMPORTLIB_MARKER(urllib.parse).quote('foo'))",
            ),
            ("ipaddress!.IPV6LENGTH", "_IMPORTLIB_MARKER(ipaddress).IPV6LENGTH"),
            ("urllib.parse!.quote('?')", "_IMPORTLIB_MARKER(urllib.parse).quote('?')"),
        ],
    )
    def test_transform_source(self, test_source: str, expected_result: str) -> None:
        retokenized_source = inline_import.transform_source(test_source)
        assert retokenized_source == expected_result

    @pytest.mark.parametrize(
        "test_source, expected_result",
        [
            ("collections!.Counter(urllib.parse!.quote('foo'))", {"f": 1, "o": 2}),
            ("ipaddress!.IPV6LENGTH", ipaddress.IPV6LENGTH),
            ("urllib.parse!.quote('?')", urllib.parse.quote("?")),
        ],
    )
    def test_parse(self, test_source: str, expected_result: typing.Any) -> None:
        tree = inline_import.parse(test_source, mode="eval")
        code = compile(tree, "<string>", "eval")
        result = eval(code)

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
    def test_invalid_attribute_syntax(self, invalid_expr: str) -> None:
        with pytest.raises(SyntaxError):
            _ = inline_import.parse(invalid_expr)

    def test_import_op_as_attr_name(self) -> None:
        with pytest.raises(SyntaxError):
            _ = inline_import.parse("a.!.b")

    @pytest.mark.parametrize("test_source", ["del a!.b", "a!.b = 1", "del a.b.c!.d", "a.b.c!.d = 1"])
    def test_del_store_import(self, test_source: str) -> None:
        # FIXME: Fix token parsing so it only allows alternating names and dots.

        tree = inline_import.parse(test_source)
        _ = compile(tree, "<string>", "exec")

    @pytest.mark.parametrize("test_source", ["del a!", "a! = 1", "del a.b!", "a.b! = 1"])
    def test_invalid_del_store_import(self, test_source: str) -> None:
        # FIXME: Change test so it doesn't hide why test_del_store_import is failing.

        with pytest.raises(
            (
                ValueError,  # raised by builtins.compile
                SyntaxError,  # raised by inline_import.parse
            )
        ):
            tree = inline_import.parse(test_source)
            _ = compile(tree, "<string>", "exec")

    def test_lone_import_op(self) -> None:
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
    def test_invalid_argument_syntax(self, invalid_source: str) -> None:
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
    def test_invalid_def_syntax(self, invalid_source: str) -> None:
        # FIXME:
        # "class X!: pass" turns into "class _IMPORTLIB_MARKER(X): pass"
        # This doesn't trip up the initial ast parsing, but the transformer doesn't find and replace the marker.
        # This results in _IMPORTLIB_MARKER being left behind and the final error being that X doesn't exist
        # to be inherited from.
        #
        # This could be preempted at the tokenizer level potentially, or fixed afterwards in the AST transformer.
        # The latter is simpler: Find all class definitions with the name _IMPORTLIB_MARKER and replace them.
        # Technically can hit false positives though. More robust to do so at the tokenizer level somehow.

        with pytest.raises(SyntaxError):
            tree = inline_import.parse(invalid_source, "<string>")
            _ = compile(tree, "<string>", "exec")

    def test_kwargs(self) -> None:
        import collections

        tree = inline_import.parse("dict(x=collections!)", mode="eval")
        code = compile(tree, "<string>", "eval")
        x = eval(code)["x"]

        assert x is collections

    @pytest.mark.parametrize(
        "test_source, annotation_var",
        [
            ("def test_func() -> typing!.Any: pass", "return"),
            ("def test_func(x: typing!.Any): pass", "x"),
            ("def test_func(x: typing!.Any = 1): pass", "x"),
        ],
    )
    def test_typehint_conversion(self, test_source: str, annotation_var: str) -> None:
        globals_: typing.Dict[str, typing.Any] = {}

        tree = inline_import.parse(test_source)
        code = compile(tree, "<string>", "exec")
        exec(code, globals_)

        test_func = globals_["test_func"]

        assert test_func.__annotations__[annotation_var] is typing.Any

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
    def test_import_statement(self, invalid_source: str) -> None:
        with pytest.raises(SyntaxError):
            _ = inline_import.parse(invalid_source, mode="exec")

    def test_importer_name_not_mangled(self) -> None:
        # If import_expression.constants.IMPORTER.startswith('__'), this will fail.
        _ = inline_import.parse("class Foo: x = io!")

    def test_bytes_input(self):
        tree = inline_import.parse(b"typing!.TYPE_CHECKING", mode="eval")
        code = compile(tree, "<string>", "eval")
        assert eval(code) == typing.TYPE_CHECKING


class TestLazyModuleImport:
    @classmethod
    def lazy_import_docs(cls, name: str) -> types.ModuleType:
        """Lazy import recipe from the importlib docs.

        Source: https://docs.python.org/3.11/library/importlib.html#implementing-lazy-imports
        """

        spec = importlib.util.find_spec(name)
        # Let presence of None cause an exception.
        loader = importlib.util.LazyLoader(spec.loader)  # type: ignore
        spec.loader = loader  # type: ignore
        module = importlib.util.module_from_spec(spec)  # type: ignore
        sys.modules[name] = module
        loader.exec_module(module)
        return module

    def test_regular_import(self):
        start_time = time.perf_counter()

        import concurrent.futures
        import contextlib
        import inspect
        import itertools
        import types
        from importlib import abc

        total_time = time.perf_counter() - start_time

        assert concurrent.futures.as_completed
        assert contextlib.contextmanager
        assert inspect.getsource
        assert itertools.chain
        assert types.ModuleType
        assert abc.MetaPathFinder

        print(f"Time taken for regular import = {total_time}")

    def test_recipe_docs(self):
        start_time = time.perf_counter()

        lazy_concurrent_futures = self.lazy_import_docs("concurrent.futures")
        lazy_contextlib = self.lazy_import_docs("contextlib")
        lazy_inspect = self.lazy_import_docs("inspect")
        lazy_itertools = self.lazy_import_docs("itertools")
        lazy_types = self.lazy_import_docs("types")
        lazy_importlib_abc = self.lazy_import_docs("importlib.abc")

        total_time = time.perf_counter() - start_time

        assert lazy_concurrent_futures.as_completed
        assert lazy_contextlib.contextmanager
        assert lazy_inspect.getsource
        assert lazy_itertools.chain
        assert lazy_types.ModuleType
        assert lazy_importlib_abc.MetaPathFinder

        print(f"Time taken for lazy import (based on importlib recipe) = {total_time}")

    def test_lazy_module_import(self):
        start_time = time.perf_counter()

        with lazy_module_import():
            import concurrent.futures
            import contextlib
            import inspect
            import itertools
            import types
            from importlib import abc

        total_time = time.perf_counter() - start_time

        assert concurrent.futures.as_completed
        assert contextlib.contextmanager
        assert inspect.getsource
        assert itertools.chain
        assert types.ModuleType
        assert abc.MetaPathFinder

        print(f"Time taken for lazy import = {total_time}")

    def test_delayed_circular_import_type_hints(self):
        from tests.sample_lazy_pkg import module1, module2

        class1_found_type_hints = typing.get_type_hints(module1.Class1.__init__)
        class2_found_type_hints = typing.get_type_hints(module2.Class2.__init__)

        assert class1_found_type_hints == {"scr": typing.Optional[module2.Class2]}
        assert class2_found_type_hints == {"scr": typing.Optional[module1.Class1]}

    @pytest.mark.skipif(sys.version_info < (3, 10), reason="requires 3.10 or higher")
    def test_delayed_circular_import_annotations(self):
        import inspect

        from tests.sample_lazy_pkg import module1, module2

        class1_init_found_annotations = inspect.get_annotations(module1.Class1.__init__, eval_str=True)
        class2_init_found_annotations = inspect.get_annotations(module2.Class2.__init__, eval_str=True)

        assert class1_init_found_annotations == {"scr": typing.Optional[module2.Class2]}
        assert class2_init_found_annotations == {"scr": typing.Optional[module1.Class1]}
