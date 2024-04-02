import shutil
from pathlib import Path


def pytest_configure(config):
    tests_path = Path("tests")
    for pth in tests_path.glob("**/__pycache__"):
        shutil.rmtree(pth)
