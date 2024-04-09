from __experimental__ import lazy_module_import

with lazy_module_import():
    import typing

    import tests.sample_lazy_pkg.module2 as module2  # noqa: PLR0402

__all__ = ("Class1",)


class Class1:
    def __init__(self, scr: "typing.Optional[module2.Class2]"):
        self.scr = scr
