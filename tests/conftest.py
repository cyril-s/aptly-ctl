import pytest
import os
import os.path
from aptly_ctl.aptly import Package


@pytest.fixture
def no_requests(monkeypatch):
    monkeypatch.delattr("requests.sessions.Session.request")


def _packages(directory: str):
    pkgs_dir = os.path.realpath(directory)
    pkgs = (os.path.join(pkgs_dir, pkg) for pkg in os.listdir(pkgs_dir))
    return [Package.from_file(pkg) for pkg in pkgs]


@pytest.fixture
def packages_simple():
    return _packages("tests/packages/simple")


@pytest.fixture
def packages_conflict():
    return _packages("tests/packages/conflict")


def pytest_addoption(parser):
    parser.addini("aptly_url", help="Aptly URL for integration tests")
    parser.addini("aptly_gpgkey", help="Aptly GPG key for integration tests")
    parser.addini(
        "aptly_passphrase_file", help="Aptly passphrase file path for integration tests"
    )


def _get_ini_or_fail(name, pytestconfig):
    value = pytestconfig.getini(name)
    if not value:
        pytest.fail(name + " is not set!")
    return value


@pytest.fixture
def aptly_url(pytestconfig):
    return _get_ini_or_fail("aptly_url", pytestconfig)


@pytest.fixture
def aptly_gpgkey(pytestconfig):
    return _get_ini_or_fail("aptly_gpgkey", pytestconfig)


@pytest.fixture
def aptly_passphrase_file(pytestconfig):
    return _get_ini_or_fail("aptly_passphrase_file", pytestconfig)
