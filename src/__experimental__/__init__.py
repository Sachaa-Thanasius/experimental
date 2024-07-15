"""Module for custom code transformations."""

__all__ = (
    "all_feature_names",
    "elide_cast",
    "inline_import",
    "late_bound_arg_defaults",
    "lazy_import",
    "lazy_module_import",
    "install_experimental_import_hook",
    "uninstall_experimental_import_hook",
)


all_feature_names = (
    "elide_cast",
    "inline_import",
    "late_bound_arg_defaults",
    "lazy_import",
)

TYPING = False

if TYPING:
    from __experimental__._core import install_experimental_import_hook, uninstall_experimental_import_hook
    from __experimental__._features.elide_cast import FEATURE as elide_cast
    from __experimental__._features.inline_import import FEATURE as inline_import
    from __experimental__._features.late_bound_arg_defaults import FEATURE as late_bound_arg_defaults
    from __experimental__._features.lazy_import import FEATURE as lazy_import, lazy_module_import


def __getattr__(name: str) -> object:
    if name in __all__:
        import importlib

        if name in all_feature_names:
            feature_mod = importlib.import_module(f"__experimental__._features.{name}")
            return feature_mod.FEATURE

        if name in {"install_experimental_import_hook", "uninstall_experimental_import_hook"}:
            core = importlib.import_module("__experimental__._core")
            return getattr(core, name)

        if name == "lazy_module_import":
            from __experimental__._features.lazy_import import lazy_module_import

            return lazy_module_import

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(__all__)
