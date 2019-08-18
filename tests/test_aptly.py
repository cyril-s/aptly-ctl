import pytest
import aptly_api
from aptly_ctl.types import Repo, Package, Snapshot
from aptly_ctl.aptly import Aptly
from aptly_ctl.exceptions import AptlyCtlError


REPOS = {
        "stretch_main": aptly_api.Repo("stretch_main", None, "stretch", "main"),
        "stretch_extra": aptly_api.Repo("stretch_extra", None, "stretch", "extra"),
        "stretch_nightly": aptly_api.Repo("stretch_nightly", None, "stretch", "nightly")
        }

SNAPSHOTS = {
        "stretch_main": aptly_api.Snapshot("stretch_main", None, None),
        "stretch_extra": aptly_api.Snapshot("stretch_extra", None, None),
        "stretch_nightly": aptly_api.Snapshot("stretch_nightly", None, None)
        }

PKGS = {
        "stretch_main": {
            None: [
                aptly_api.Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
                aptly_api.Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
                ],
            "python": [
                aptly_api.Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
                aptly_api.Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                ],
            "aptly": [
                aptly_api.Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
                ],
            "nginx": [],
            },
        "stretch_extra": {
            None: [
                aptly_api.Package("Pall nginx 1.12.0 9a4063c2d0b3d196", None, None, None),
                aptly_api.Package("Pall nginx 1.14.2-2 b38c3dcc478ddaf", None, None, None),
                ],
            "python": [],
            "aptly": [],
            "nginx": [
                aptly_api.Package("Pall nginx 1.12.0 9a4063c2d0b3d196", None, None, None),
                aptly_api.Package("Pall nginx 1.14.2-2 b38c3dcc478ddaf", None, None, None),
                ],
            },
        "stretch_nightly": {
            None: [
                aptly_api.Package("Pamd64 python 3.6.6-3 3660000000000000", None, None, None),
                aptly_api.Package("Pamd64 aptly 1.5.0-3 1500000000000000", None, None, None),
                ],
            "python": [
                aptly_api.Package("Pamd64 python 3.6.6-3 3660000000000000", None, None, None),
                ],
            "aptly": [
                aptly_api.Package("Pamd64 aptly 1.5.0-3 1500000000000000", None, None, None),
                ],
            "nginx": [],
            },
        }


def mocked_search(self, name, query, *args, **kwargs):
    try:
        return PKGS[name].get(query, [])
    except KeyError:
        raise aptly_api.AptlyAPIException(
            "Repo/Snapshot {} not found".format(name), status_code=404)

def mocked_repo_show(self, name):
    try:
        return REPOS[name]
    except KeyError:
        raise aptly_api.AptlyAPIException(
            "Repo {} not found".format(name), status_code=404)

def mocked_snapshot_show(self, name):
    try:
        return SNAPSHOTS[name]
    except KeyError:
        raise aptly_api.AptlyAPIException(
            "Snapshot {} not found".format(name), status_code=404)

def mocked_repo_list(self):
    return list(REPOS.values())

def mocked_snapshot_list(self):
    return list(SNAPSHOTS.values())

@pytest.fixture
def mock_search(monkeypatch):
    monkeypatch.setattr(
        aptly_api.parts.repos.ReposAPISection,
        "show",
        mocked_repo_show
        )
    monkeypatch.setattr(
        aptly_api.parts.repos.ReposAPISection,
        "list",
        mocked_repo_list
        )
    monkeypatch.setattr(
        aptly_api.parts.snapshots.SnapshotAPISection,
        "show",
        mocked_snapshot_show
        )
    monkeypatch.setattr(
        aptly_api.parts.snapshots.SnapshotAPISection,
        "list",
        mocked_snapshot_list
        )
    monkeypatch.setattr(
        aptly_api.parts.snapshots.SnapshotAPISection,
        "list_packages",
        mocked_search
        )
    monkeypatch.setattr(
        aptly_api.parts.repos.ReposAPISection,
        "search_packages",
        mocked_search
        )


class TestAptly:

    def test_repo_search(self, no_requests, mock_search):
        a = Aptly("http://localhost:8080/api")
        def build_expected(repo, query):
            return Repo.from_aptly_api(
                REPOS[repo],
                frozenset(Package.from_aptly_api(pkg) for pkg in PKGS[repo][query]))
        for args, expected in [
                (
                    ["stretch_main"],
                    build_expected("stretch_main", None)
                    ),
                (
                    ["stretch_main", "aptly"],
                    build_expected("stretch_main", "aptly")
                    ),
                (
                    ["stretch_main", "bla"],
                    Repo.from_aptly_api(REPOS["stretch_main"], frozenset())
                    ),
                (
                    [Repo.from_aptly_api(REPOS["stretch_main"])],
                    build_expected("stretch_main", None)
                    ),
                ]:
            result = a.repo_search(*args)
            assert result == expected

    def test_repo_search_err(self, no_requests, mock_search):
        a = Aptly("http://localhost:8080/api")
        with pytest.raises(AptlyCtlError):
            a.repo_search("bla")

    def test_snapshot_search(self, no_requests, mock_search):
        a = Aptly("http://localhost:8080/api")
        def build_expected(snapshot, query):
            return Snapshot.from_aptly_api(
                SNAPSHOTS[snapshot],
                frozenset(Package.from_aptly_api(pkg) for pkg in PKGS[snapshot][query]))
        for args, expected in [
                (
                    ["stretch_main"],
                    build_expected("stretch_main", None)
                    ),
                (
                    ["stretch_main", "aptly"],
                    build_expected("stretch_main", "aptly")
                    ),
                (
                    ["stretch_main", "bla"],
                    Snapshot.from_aptly_api(SNAPSHOTS["stretch_main"], frozenset())
                    ),
                (
                    [Snapshot.from_aptly_api(SNAPSHOTS["stretch_main"])],
                    build_expected("stretch_main", None)
                    ),
                ]:
            result = a.snapshot_search(*args)
            assert result == expected

    def test_snapshot_search_err(self, no_requests, mock_search):
        a = Aptly("http://localhost:8080/api")
        with pytest.raises(AptlyCtlError):
            a.snapshot_search("bla")

    def test_search(self, no_requests, mock_search):
        a = Aptly("http://localhost:8080/api")
        def build_expected(repos, snapshots, queries):
            expected = set()
            for repo in repos:
                packages = []
                for query in queries:
                    packages.extend(
                        Package.from_aptly_api(pkg) for pkg in PKGS[repo][query])
                expected.add(Repo.from_aptly_api(REPOS[repo], frozenset(packages)))
            for snapshot in snapshots:
                packages = []
                for query in queries:
                    packages.extend(
                        Package.from_aptly_api(pkg) for pkg in PKGS[snapshot][query])
                expected.add(Snapshot.from_aptly_api(SNAPSHOTS[snapshot], frozenset(packages)))
            return expected
        for kwargs, expected in [
                (
                    {},
                    build_expected(
                        repos=["stretch_main", "stretch_extra", "stretch_nightly"],
                        snapshots=["stretch_main", "stretch_extra", "stretch_nightly"],
                        queries=[None],
                        ),
                    ),
                (
                    {"queries": ["aptly"]},
                    build_expected(
                        repos=["stretch_main", "stretch_nightly"],
                        snapshots=["stretch_main", "stretch_nightly"],
                        queries=["aptly"],
                        ),
                    ),
                (
                    {"queries": ["aptly", "aptly"]},
                    build_expected(
                        repos=["stretch_main", "stretch_nightly"],
                        snapshots=["stretch_main", "stretch_nightly"],
                        queries=["aptly"],
                        ),
                    ),
                (
                    {"queries": ["aptly", "python"]},
                    build_expected(
                        repos=["stretch_main", "stretch_nightly"],
                        snapshots=["stretch_main", "stretch_nightly"],
                        queries=["aptly", "python"],
                        ),
                    ),
                # only repos
                (
                    {"queries": ["python"], "repos": ["stretch_nightly"]},
                    build_expected(
                        repos=["stretch_nightly"],
                        snapshots=[],
                        queries=["python"],
                        ),
                    ),
                (
                    {
                        "queries": ["python"],
                        "repos": ["stretch_nightly", "stretch_nightly"],
                        },
                    build_expected(
                        repos=["stretch_nightly"],
                        snapshots=[],
                        queries=["python"],
                        ),
                    ),
                (
                    {
                        "queries": ["python"],
                        "repos": ["stretch_main", "stretch_nightly"],
                        },
                    build_expected(
                        repos=["stretch_main", "stretch_nightly"],
                        snapshots=[],
                        queries=["python"],
                        ),
                    ),
                (
                    {"queries": ["python"], "repos": "*"},
                    build_expected(
                        repos=["stretch_main", "stretch_nightly"],
                        snapshots=[],
                        queries=["python"],
                        ),
                    ),
                # only snapshots
                (
                    {"queries": ["python"], "snapshots": ["stretch_nightly"]},
                    build_expected(
                        repos=[],
                        snapshots=["stretch_nightly"],
                        queries=["python"],
                        ),
                    ),
                (
                    {
                        "queries": ["python"],
                        "snapshots": ["stretch_nightly", "stretch_nightly"],
                        },
                    build_expected(
                        repos=[],
                        snapshots=["stretch_nightly"],
                        queries=["python"],
                        ),
                    ),
                (
                    {
                        "queries": ["python"],
                        "snapshots": ["stretch_main", "stretch_nightly"],
                        },
                    build_expected(
                        repos=[],
                        snapshots=["stretch_main", "stretch_nightly"],
                        queries=["python"],
                        ),
                    ),
                (
                    {"queries": ["python"], "snapshots": "*"},
                    build_expected(
                        repos=[],
                        snapshots=["stretch_main", "stretch_nightly"],
                        queries=["python"],
                        ),
                    ),
                ]:
            result = a.search(**kwargs)
            assert set(result[0]) == expected
            assert not result[1]

    def test_search_err(self, no_requests, mock_search):
        a = Aptly("http://localhost:8080/api")
        for kwargs in [
                {"repos": ["bla"]},
                {"snapshots": ["bla"]},
                ]:
            result = a.search(**kwargs)
            assert not result[0]
            assert len(result[1]) == 1
            assert isinstance(result[1][0], AptlyCtlError)

    def test_snapshot_diff(self, no_requests, monkeypatch):
        a = Aptly("http://localhost:8080/api")
        def mocked_diff(*args):
            return [
                {
                    "Left": "Pamd64 python 3.6.6 3660000000000000",
                    "Right": None
                    },
                {
                    "Left": None,
                    "Right": "Pamd64 aptly 1.5.0-3 1500000000000000"
                    },
                {
                    "Left": "Pall nginx 1.12.0 9a4063c2d0b3d196",
                    "Right": "Pall nginx 1.12.0 5555555555555555",
                    },
                ]
        monkeypatch.setattr(
            aptly_api.parts.snapshots.SnapshotAPISection, "diff", mocked_diff)
        diff = a.snapshot_diff("snap1", "snap2")
        assert diff == [
            (Package.from_key("Pamd64 python 3.6.6 3660000000000000"), None),
            (None, Package.from_key("Pamd64 aptly 1.5.0-3 1500000000000000")),
            (
                Package.from_key("Pall nginx 1.12.0 9a4063c2d0b3d196"),
                Package.from_key("Pall nginx 1.12.0 5555555555555555"),
                ),
            ]
