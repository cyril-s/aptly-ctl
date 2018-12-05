from . context import aptly_ctl
from aptly_ctl.subcommands.search import rotate, search, config_subparser
from aptly_ctl.utils import PackageRef
import aptly_api
from aptly_api import Package
import argparse
import pytest

pseudo_repo = {
        aptly_api.Repo("stretch_main", None, None, None): [
                (
                    Package("Pamd64 aptly 1.3.0+ds1-2 f7673868294f03c1", None, None, None),
                    ["aptly"] # found by these queries
                ),
                (
                    Package("Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0", None, None, None),
                    ["python3.6", "Name (% python3*)", "Name (~ python3.*)"]
                )
            ],
        aptly_api.Repo("stretch_extra", None, None, None): [
                (
                    Package("Pall python3-pip 9.0.1-2.3 52e9433afcb1e613", None, None, None),
                    ["python3-pip", "Name (% python3*)", "Name (~ python3.*)"]
                ),
                (
                    Package("Pall python3-wheel 0.30.0-0.2 dca6d5ca7e3f5e6f", None, None, None),
                    ["python3-wheel", "Name (% python3*)", "Name (~ python3.*)"]
                )
            ],
        aptly_api.Repo("stretch_nightly", None, None, None): [
                (
                    Package("Pall python3-setuptools 40.5.0-1 4d5a70b19b984324", None, None, None),
                    ["python3-setuptools", "Name (% python3*)", "Name (~ python3.*)"]
                )
            ]
        }

@pytest.fixture(scope="module")
def mocked_repos_list():
    return lambda class_self: pseudo_repo.keys()

@pytest.fixture(scope="module")
def mocked_repos_search_packages():
    def tmp(class_self, reponame, query=None, with_deps=False, detailed=False):
        searched_repo = aptly_api.Repo(reponame, None, None, None)
        if searched_repo in pseudo_repo:
            if query is not None:
                all_packages = pseudo_repo[searched_repo]
                result = [ p[0] for p in all_packages if query in p[1] ]
            else:
                result = [ p[0] for p in all_packages ]
        else:
            raise aptly_api.AptlyAPIException("404 - Not Found - local repo with name {} not found".format(reponame), status_code=404)
        return result
    return tmp

@pytest.fixture(scope="module")
def arg_parser():
    parser, subparsers = aptly_ctl.application.config_parser()
    config_subparser(subparsers)
    return parser

@pytest.fixture(scope="module")
def config():
    cfg_overrides = [
            "url=http://localhost:8090",
            "signing.gpgkey=111111",
            "signing.passphrase_file=/etc/pass"
            ]
    return aptly_ctl.Config.Config(False, cfg_overrides=cfg_overrides)

@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    monkeypatch.delattr("requests.sessions.Session.request")

def test_rotate_positive():
    a = [
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]
    b = rotate(a, 2)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == [
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            ]

def test_rotate_negative():
    a = [
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]
    b = rotate(a, -2)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == [
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            ]

def test_rotate_zero():
    a = [
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]
    b = rotate(a, 0)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == [
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            ]

def test_rotate_different_architectures():
    a = [
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pi386 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pi386 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pi386 python 3.6.6 3660000000000000", None, None, None),
            Package("Pi386 python 3.6.5 3650000000000000", None, None, None),
            ]
    b = rotate(a, 1)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == [
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pi386 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pi386 python 3.6.5 3650000000000000", None, None, None),
            ]

def test_rotate_different_prefixes():
    a = [
            Package("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("prefPamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("prefPamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("somePamd64 python 3.6.6 3660000000000000", None, None, None),
            Package("somePamd64 python 3.6.5 3650000000000000", None, None, None),
            ]
    b = rotate(a, 1)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == [
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("prefPamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            Package("somePamd64 python 3.6.5 3650000000000000", None, None, None),
            ]

def test_rotate_positive_out_of_range():
    a = [
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]
    b = rotate(a, 10)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == []

def test_rotate_negative_out_of_range():
    a = [
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]
    b = rotate(a, -10)
    b.sort(key=lambda s: PackageRef(s.key))
    assert b == [
            Package("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            Package("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            Package("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            Package("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            Package("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]

def test_search_single_query_with_single_result(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "python3.6"])
    rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert rc == 0
    assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n'

def test_search_single_query_with_multiple_results(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "Name (% python3*)"])
    rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert rc == 0
    assert stdout == '"stretch_extra/Pall python3-pip 9.0.1-2.3 52e9433afcb1e613"\n' + \
                    '"stretch_extra/Pall python3-wheel 0.30.0-0.2 dca6d5ca7e3f5e6f"\n' + \
                    '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                    '"stretch_nightly/Pall python3-setuptools 40.5.0-1 4d5a70b19b984324"\n'

def test_search_multiple_queries(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "python3.6", "aptly"])
    rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert rc == 0
    assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                    '"stretch_main/Pamd64 aptly 1.3.0+ds1-2 f7673868294f03c1"\n'

def test_search_in_one_repo(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "-r", "stretch_main", "Name (% python3*)"])
    rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert rc == 0
    assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n'

def test_search_in_multiple_repos(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "-r", "stretch_main", "-r", "stretch_nightly", "Name (% python3*)"])
    rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert rc == 0
    assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                    '"stretch_nightly/Pall python3-setuptools 40.5.0-1 4d5a70b19b984324"\n'

def test_search_name_search_shortcut(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "-n", "python3.*"])
    rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert rc == 0
    assert stdout == '"stretch_extra/Pall python3-pip 9.0.1-2.3 52e9433afcb1e613"\n' + \
                    '"stretch_extra/Pall python3-wheel 0.30.0-0.2 dca6d5ca7e3f5e6f"\n' + \
                    '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                    '"stretch_nightly/Pall python3-setuptools 40.5.0-1 4d5a70b19b984324"\n'

def test_search_non_existent_repo(arg_parser, config, capsys, monkeypatch, mocked_repos_list, mocked_repos_search_packages):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "-r", "blabla", "python3.6"])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""
    assert e._excinfo[1].args[0].status_code == 404
    assert "local repo with name blabla not found" in e._excinfo[1].args[0].args[0].lower()

def test_search_no_repos(arg_parser, config, capsys, monkeypatch):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", lambda *args: [])
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", lambda *args: [])
    args = arg_parser.parse_args(["search", "python3.6"])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""

def test_search_incorrect_query(arg_parser, config, capsys, monkeypatch, mocked_repos_list):
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repos_list)
    def mocked_repos_search_packages(*args):
        raise aptly_api.AptlyAPIException("400 - Bad Request - parsing failed: unexpected token <EOL>: expecting ')'", status_code=400)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repos_search_packages)
    args = arg_parser.parse_args(["search", "Name (~ python3.*"])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = search(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""
    assert 'Bad query "Name (~ python3.*": unexpected token <EOL>: expecting \')\'' in e._excinfo[1].args[0]
