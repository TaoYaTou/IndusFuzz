import os
import sys
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import reset_and_reload_all  # noqa: E402  # noqa: E402


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_TEST_PKGS = os.path.join(_PROJECT_ROOT, ".test_pkgs")
if os.path.isdir(_TEST_PKGS) and _TEST_PKGS not in sys.path:
    sys.path.insert(0, _TEST_PKGS)


@pytest.fixture
def fresh_registry():
    """Clear registry and re-register all 7 built-in protocols.

    Tests that need a clean, fully-populated registry should request this
    fixture explicitly.
    """
    _r = reset_and_reload_all()
    yield _r
    _r._PROTOCOLS.clear()


@pytest.fixture
def tmp_report_dir():
    d = tempfile.mkdtemp(prefix="indusfuzz_report_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def clean_env():
    _ENV_KEYS = ["INDUSFUZZ_HOME", "INDUSFUZZ_CONFIG", "INDUSFUZZ_REPORTS", "PYTHONIOENCODING"]
    saved = {}
    for k in _ENV_KEYS:
        saved[k] = os.environ.get(k)
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def sample_modbus_payload():
    return bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00])


@pytest.fixture
def sample_payload_10():
    return bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00])


@pytest.fixture
def sample_payload_12():
    return bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
