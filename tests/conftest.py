import os.path
import shutil


def pytest_configure(config):
    pth = "tests/__pycache__"
    if os.path.exists(pth):
        shutil.rmtree(pth)
