import os
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--binary-path", action="store", default=None, help="Path to the binary"
    )


@pytest.fixture
def binary_path(request):
    binary_path_value = request.config.getoption("--binary-path")
    if binary_path_value is None:
        binary_path_value = os.environ.get("TEST_STOCKFISH_BINARY", "stockfish")

    return binary_path_value
