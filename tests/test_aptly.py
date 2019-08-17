import pytest
import aptly_api
from aptly_ctl.types import Repo, Package
from aptly_ctl.aptly import Aptly
from aptly_ctl.exceptions import AptlyCtlError


REPOS = {
        "stretch_main": aptly_api.Repo("stretch_main", None, "stretch", "main"),
        "stretch_extra": aptly_api.Repo("stretch_extra", None, "stretch", "extra"),
        "stretch_nightly": aptly_api.Repo("stretch_nightly", None, "stretch", "nightly")
        }

PKGS = {
        "stretch_main": {
            "": [
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
            "": [
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
            "": [
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


def mock_search(self, repo, query, *args, **kwargs):
    try:
        return PKGS[repo].get(query, [])
    except KeyError:
        raise aptly_api.AptlyAPIException("Repo {} not found".format(repo),
                                          status_code=404)

def mock_repo_show(self, name):
    try:
        return REPOS[name]
    except KeyError:
        raise aptly_api.AptlyAPIException("Repo {} not found".format(name),
                                          status_code=404)

def mock_repo_list(self):
    return list(REPOS.values())


class TestAptly:

    def test_repo_search(self, no_requests, monkeypatch):
        a = Aptly("http://localhost:8080/api")

        def build_expected(repo, query):
            return Repo.fromAptlyApi(
                REPOS[repo],
                frozenset(Package.fromAptlyApi(pkg) for pkg in PKGS[repo][query]))

        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "show", mock_repo_show)
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "search_packages", mock_search)
        for args, expected in [
                (
                    ["stretch_main"],
                    build_expected("stretch_main", "")
                    ),
                (
                    ["stretch_main", "aptly"],
                    build_expected("stretch_main", "aptly")
                    ),
                (
                    ["stretch_main", "bla"],
                    Repo.fromAptlyApi(REPOS["stretch_main"], frozenset())
                    ),
                (
                    [REPOS["stretch_main"]],
                    build_expected("stretch_main", "")
                    ),
                ]:
            result = a.repo_search(*args)
            assert result == expected

    def test_repo_search_err(self, no_requests, monkeypatch):
        a = Aptly("http://localhost:8080/api")
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection,
                            "show", mock_repo_show)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection,
                            "search_packages", mock_search)
        with pytest.raises(AptlyCtlError):
            a.repo_search("bla")

    def test_search(self, no_requests, monkeypatch):
        a = Aptly("http://localhost:8080/api")
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "show", mock_repo_show)
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "list", mock_repo_list)
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "search_packages", mock_search)

        def build_expected(repos, queries):
            expected = set()
            for repo in repos:
                packages = []
                for query in queries:
                    packages.extend(
                        Package.fromAptlyApi(pkg) for pkg in PKGS[repo][query])
                expected.add(Repo.fromAptlyApi(REPOS[repo], frozenset(packages)))
            return expected

        for kwargs, expected in [
                (
                    {"queries": ["aptly"]},
                    build_expected(
                        ["stretch_main", "stretch_nightly"], ["aptly"]),
                    ),
                (
                    {"queries": ["aptly", "aptly"]},
                    build_expected(
                        ["stretch_main", "stretch_nightly"], ["aptly"]),
                    ),
                (
                    {},
                    build_expected(
                        ["stretch_main", "stretch_extra", "stretch_nightly"],
                        [""]),
                    ),
                (
                    {"queries": ["aptly", "python"]},
                    build_expected(
                        ["stretch_main", "stretch_nightly"],
                        ["aptly", "python"]),
                    ),
                (
                    {"queries": ["python"], "repos": ["stretch_nightly"]},
                    build_expected(
                        ["stretch_nightly"], ["python"]),
                    ),
                (
                    {
                        "queries": ["python"],
                        "repos": ["stretch_nightly", "stretch_nightly"]
                        },
                    build_expected(
                        ["stretch_nightly"], ["python"]),
                    ),
                (
                    {
                        "queries": ["python"],
                        "repos": ["stretch_main", "stretch_nightly"]
                        },
                    build_expected(
                        ["stretch_main", "stretch_nightly"], ["python"]),
                    ),
                ]:
            result = a.search(**kwargs)
            assert set(result[0]) == expected
            assert not result[1]

    def test_search_err(self, no_requests, monkeypatch):
        a = Aptly("http://localhost:8080/api")
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "show", mock_repo_show)
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "list", mock_repo_list)
        monkeypatch.setattr(
            aptly_api.parts.repos.ReposAPISection, "search_packages", mock_search)
        result = a.search(repos=["bla"])
        assert not result[0]
        assert len(result[1]) == 1
        assert isinstance(result[1][0], AptlyCtlError)
