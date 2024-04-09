from __experimental__ import lazy_module_import

with lazy_module_import():
    import typing

    import tests.sample_lazy_pkg.module1 as module1  # noqa: PLR0402

__all__ = ("Class2",)


class Class2:
    def __init__(self, scr: "typing.Optional[module1.Class1]"):
        self.scr = scr
