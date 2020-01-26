import pytest
import random
import os
import os.path
from aptly_ctl.debian import Package


@pytest.fixture
def no_requests(monkeypatch):
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture
def packages_simple():
    pkgs_dir = os.path.realpath("tests/packages/simple")
    pkgs = (os.path.join(pkgs_dir, pkg) for pkg in os.listdir(pkgs_dir))
    return frozenset(Package.from_file(pkg) for pkg in pkgs)


@pytest.fixture
def packages_conflict():
    pkgs_dir = os.path.realpath("tests/packages/conflict")
    pkgs = (os.path.join(pkgs_dir, pkg) for pkg in os.listdir(pkgs_dir))
    return frozenset(Package.from_file(pkg) for pkg in pkgs)
