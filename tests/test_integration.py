import importlib.util
import pathlib
from contextlib import contextmanager

from __experimental__._core import _ExperimentalLoader


def test_loader_with_multiple_features(tmp_path: pathlib.Path):
    sample_text = """\
from typing import cast

from __experimental__ import inline_import, late_bound_arg_defaults

def example_func(
    z: float,
    a: int = 1,
    b: list[int] => ([a] * a),
    /,
    c: dict[str, int] => ({str(a): b}),
    *,
    d: str => (str(z) + str(c)),
) -> str:
    thing = cast(int, contextlib!.contextmanager)
    return [thing, d]
"""

    # Boilerplate to dynamically create and load this module.
    tmp_init = tmp_path / "__init__.py"
    tmp_init.touch()
    tmp_file = tmp_path / "sample.py"
    tmp_file.write_text(sample_text, encoding="utf-8")

    module_name = "sample"
    path = tmp_file.resolve()

    spec = importlib.util.spec_from_file_location(module_name, path, loader=_ExperimentalLoader(module_name, str(path)))

    assert spec
    assert spec.loader

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    example_func = module.example_func

    thing, d = example_func(2.0, 3)
    assert thing is contextmanager
    assert d == "2.0{'3': [3, 3, 3]}"
