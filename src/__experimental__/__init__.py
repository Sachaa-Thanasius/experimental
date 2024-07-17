# pyright: reportUnsupportedDunderAll=none
"""A handful of custom code transformations."""

__all__ = (
    # Not features
    "all_feature_names",
    "install_experimental_import_hook",
    "uninstall_experimental_import_hook",
    # Features
    "elide_cast",
    "inline_import",
    "late_bound_arg_defaults",
    "lazy_import",
    "lazy_module_import",
)


from __experimental__._core import (
    install_experimental_import_hook,
    uninstall_experimental_import_hook,
)


# Keep __all__ and this in sync.
all_feature_names = (
    "elide_cast",
    "inline_import",
    "late_bound_arg_defaults",
    "lazy_import",
    "lazy_module_import",
)


def __getattr__(name: str) -> object:
    if name in all_feature_names:
        from __experimental__._core import _ExperimentalFeature

        return _ExperimentalFeature._registry[name]

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(__all__)
