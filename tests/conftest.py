import shutil
from pathlib import Path


def pytest_configure(config) -> None:
    tests_path = Path("tests")
    shutil.rmtree(tests_path / "__pycache__")
    for pth in tests_path.glob("**/__pycache__"):
        shutil.rmtree(pth)
