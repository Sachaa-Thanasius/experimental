# This whole file is modified from future-fstrings and future-breakpoint.

import distutils
import os.path

from setuptools import setup
from setuptools.command.install import install as _install

PTH = (
    "try:\n"
    "    import experimental\n"
    "except ImportError:\n"
    "    pass\n"
    "else:\n"
    "    experimental.install()\n"
)


class install(_install):
    def initialize_options(self) -> None:
        super().initialize_options()

        contents = f"import sys; exec({PTH!r})\n"
        self.extra_path = (self.distribution.metadata.name, contents)

    def finalize_options(self) -> None:
        super().finalize_options()

        if self.install_lib.endswith(self.extra_path[1]):
            self.install_lib = self.install_libbase
            distutils.log.info(
                "will install .pth to '%s.pth'",
                os.path.join(self.install_lib, self.extra_path[0]),  # noqa: PTH118
            )
        else:
            distutils.log.info("skipping install of .pth during easy-install")


setup(cmdclass={"install": install})
