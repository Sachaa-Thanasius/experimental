from __experimental__ import lazy_module_import

with lazy_module_import:
    import tests.lazy_module_import.sample_pkg.module2 as module2  # noqa: PLR0402

__all__ = ("Class1",)


class Class1:
    def __init__(self, scr: "module2.Class2 | None"):
        self.scr = scr
