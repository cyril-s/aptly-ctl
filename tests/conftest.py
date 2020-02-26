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
