from __experimental__._features.lazy_import import lazy_module_import
from __experimental__.base import (
    inline_import,
    install,
    late_bound_arg_defaults,
    lazy_import,
    uninstall,
)

all_feature_names = (
    "inline_import",
    "late_bound_arg_defaults",
    "lazy_import",
)

__all__ = (
    "all_feature_names",
    "inline_import",
    "late_bound_arg_defaults",
    "lazy_module_import",
    "lazy_import",
    "install",
    "uninstall",
)
