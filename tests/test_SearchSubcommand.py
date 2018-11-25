from . context import aptly_ctl
from aptly_api.parts.packages import Package
from aptly_ctl.subcommands.search import rotate, search, config_subparser
from aptly_ctl.utils import PackageRef, ExtendedAptlyClient
import aptly_ctl.application
import aptly_ctl.Config
import aptly_api
from aptly_api import Package, Repo, AptlyAPIException
from aptly_ctl.exceptions import AptlyCtlError
import argparse
import pytest

class TestSearchSubcommand:

    pseudo_repo = {
            Repo(name="stretch_main", comment=None, default_distribution=None, default_component=None): [
                    (
                        Package(key="Pamd64 aptly 1.3.0+ds1-2 f7673868294f03c1", short_key=None, files_hash=None, fields=None),
                        ["aptly"] # found by these queries
                    ),
                    (
                        Package(key="Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0", short_key=None, files_hash=None, fields=None),
                        ["python3.6", "Name (% python3*)", "Name (~ python3.*)"]
                    )
                ],
            Repo(name="stretch_extra", comment=None, default_distribution=None, default_component=None): [
                    (
                        Package(key="Pall python3-pip 9.0.1-2.3 52e9433afcb1e613", short_key=None, files_hash=None, fields=None),
                        ["python3-pip", "Name (% python3*)", "Name (~ python3.*)"]
                    ),
                    (
                        Package(key="Pall python3-wheel 0.30.0-0.2 dca6d5ca7e3f5e6f", short_key=None, files_hash=None, fields=None),
                        ["python3-wheel", "Name (% python3*)", "Name (~ python3.*)"]
                    )
                ],
            Repo(name="stretch_nightly", comment=None, default_distribution=None, default_component=None): [
                    (
                        Package(key="Pall python3-setuptools 40.5.0-1 4d5a70b19b984324", short_key=None, files_hash=None, fields=None),
                        ["python3-setuptools", "Name (% python3*)", "Name (~ python3.*)"]
                    )
                ]
            }

    @pytest.fixture(scope="class")
    def mocked_repo_list(self):
        return lambda class_self: self.pseudo_repo.keys() 

    @pytest.fixture(scope="class")
    def mocked_repo_search_packages(self):
        def tmp(class_self, reponame, query=None, with_deps=False, detailed=False):
            searched_repo = Repo(name=reponame, comment=None, default_distribution=None, default_component=None)
            if searched_repo in self.pseudo_repo:
                if query is not None:
                    all_packages = self.pseudo_repo[searched_repo]
                    result = [ p[0] for p in all_packages if query in p[1] ]
                else:
                    result = [ p[0] for p in all_packages ]
            else:
                raise AptlyAPIException("404 - Not Found - local repo with name {} not found".format(reponame), status_code=404)
            return result
        return tmp

    @pytest.fixture(scope="class")
    def arg_parser(self):
        parser, subparsers = aptly_ctl.application.config_parser()
        config_subparser(subparsers)
        return parser

    @pytest.fixture(scope="class")
    def config(self):
        cfg_overrides = [
                "url=http://localhost:8090",
                "signing.gpgkey=111111",
                "signing.passphrase_file=/etc/pass"
                ]
        return aptly_ctl.Config.Config(False, cfg_overrides=cfg_overrides)

    @pytest.fixture(autouse=True)
    def no_requests(self, monkeypatch):
        monkeypatch.delattr("requests.sessions.Session.request")

    def test_rotate_positive(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 2)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_negative(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, -2)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_zero(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 0)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_different_architectures(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 1)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_different_prefixes(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="prefPamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="prefPamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="somePamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="somePamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 1)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="prefPamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="somePamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_positive_out_of_range(self):
        a = [
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 10)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == []

    def test_rotate_negative_out_of_range(self):
        a = [
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, -10)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_search_single_query_with_single_result(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "python3.6"])
        rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert rc == 0
        assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n'

    def test_search_single_query_with_multiple_results(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "Name (% python3*)"])
        rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert rc == 0
        assert stdout == '"stretch_extra/Pall python3-pip 9.0.1-2.3 52e9433afcb1e613"\n' + \
                        '"stretch_extra/Pall python3-wheel 0.30.0-0.2 dca6d5ca7e3f5e6f"\n' + \
                        '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                        '"stretch_nightly/Pall python3-setuptools 40.5.0-1 4d5a70b19b984324"\n'

    def test_search_multiple_queries(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "python3.6", "aptly"])
        rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert rc == 0
        assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                        '"stretch_main/Pamd64 aptly 1.3.0+ds1-2 f7673868294f03c1"\n'

    def test_search_in_one_repo(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "-r", "stretch_main", "Name (% python3*)"])
        rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert rc == 0
        assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n'

    def test_search_in_multiple_repos(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "-r", "stretch_main", "-r", "stretch_nightly", "Name (% python3*)"])
        rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert rc == 0
        assert stdout == '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                        '"stretch_nightly/Pall python3-setuptools 40.5.0-1 4d5a70b19b984324"\n'

    def test_search_name_search_shortcut(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "-n", "python3.*"])
        rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert rc == 0
        assert stdout == '"stretch_extra/Pall python3-pip 9.0.1-2.3 52e9433afcb1e613"\n' + \
                        '"stretch_extra/Pall python3-wheel 0.30.0-0.2 dca6d5ca7e3f5e6f"\n' + \
                        '"stretch_main/Pamd64 python3.6 3.6.7-1 656e12e8d5fa96a0"\n' + \
                        '"stretch_nightly/Pall python3-setuptools 40.5.0-1 4d5a70b19b984324"\n'

    def test_search_non_existent_repo(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list, mocked_repo_search_packages):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "-r", "blabla", "python3.6"])
        with pytest.raises(AptlyCtlError) as e:
            rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert stdout == ""
        assert e._excinfo[1].args[0].status_code == 404
        assert "local repo with name blabla not found" in e._excinfo[1].args[0].args[0].lower()

    def test_search_no_repos(self, arg_parser, config, capsys, monkeypatch):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", lambda *args: [])
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", lambda *args: [])
        args = arg_parser.parse_args(["search", "python3.6"])
        with pytest.raises(AptlyCtlError) as e:
            rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert stdout == ""

    def test_search_incorrect_query(self, arg_parser, config, capsys, monkeypatch, mocked_repo_list):
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "list", mocked_repo_list)
        def mocked_repo_search_packages(*args):
            raise AptlyAPIException("400 - Bad Request - parsing failed: unexpected token <EOL>: expecting ')'", status_code=400)
        monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "search_packages", mocked_repo_search_packages)
        args = arg_parser.parse_args(["search", "Name (~ python3.*"])
        with pytest.raises(AptlyCtlError) as e:
            rc = search(config, args)
        stdout, _ = capsys.readouterr()
        assert stdout == ""
        assert 'Bad query "Name (~ python3.*": unexpected token <EOL>: expecting \')\'' in e._excinfo[1].args[0]

