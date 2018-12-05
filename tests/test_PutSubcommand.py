from . context import aptly_ctl
import argparse
import pytest
import aptly_api
import re


@pytest.fixture(scope="module")
def arg_parser():
    parser, subparsers = aptly_ctl.application.config_parser()
    aptly_ctl.subcommands.put.config_subparser(subparsers)
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


def test_non_existent_repo(arg_parser, config, monkeypatch, capsys, tmpdir):
    def _repo_show(class_self, reponame):
        raise aptly_api.AptlyAPIException(status_code=404)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "show", _repo_show)
    args = arg_parser.parse_args(["put", "stretch_main", str(tmpdir.join("some.deb"))])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = aptly_ctl.subcommands.put.put(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""
    assert "local repo 'stretch_main' not found" in e._excinfo[1].args[0].lower()


def test_non_existend_file(arg_parser, config, monkeypatch, capsys, tmpdir):
    def _repo_show(class_self, reponame):
        return aptly_api.Repo("stretch_main", None, None, None)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "show", _repo_show)
    deb_path = str(tmpdir.join("some.deb"))
    args = arg_parser.parse_args(["put", "stretch_main", deb_path])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = aptly_ctl.subcommands.put.put(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""
    assert re.search("no such file or directory.*{}".format(deb_path), e._excinfo[1].args[0],
            re.IGNORECASE)


def test_existent_and_non_existend_file(arg_parser, config, monkeypatch, capsys, tmpdir):
    def _repo_show(class_self, reponame):
        return aptly_api.Repo("stretch_main", None, None, None)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "show", _repo_show)
    efile = str(tmpdir.join("efile.deb"))
    nefile = str(tmpdir.join("nefile.deb"))
    with open(efile, 'w') as f:
        f.write("test")
    args = arg_parser.parse_args(["put", "stretch_main", efile, nefile])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = aptly_ctl.subcommands.put.put(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""
    assert re.search("no such file or directory.*{}".format(nefile), e._excinfo[1].args[0],
            re.IGNORECASE)


def test_error_if_nothing_added(arg_parser, config, monkeypatch, capsys, tmpdir):
    def _repo_show(class_self, reponame):
        return aptly_api.Repo("stretch_main", None, None, None)

    def _files_upload(class_self, destination, *files):
        return ["stretch_main_123123/some.deb"]

    def _files_delete(class_self, path=None):
        pass

    def _repo_add_uploaded_file(*args, **kwargs):
        return aptly_api.FileReport(
                failed_files=["some.deb"],
                report={"Warnings": ["failed to add some.deb"], "Added": [], "Removed": []}
                )

    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "show", _repo_show)
    monkeypatch.setattr(aptly_api.parts.files.FilesAPISection, "upload", _files_upload)
    monkeypatch.setattr(aptly_api.parts.files.FilesAPISection, "delete", _files_delete)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "add_uploaded_file",
            _repo_add_uploaded_file)
    deb_path = str(tmpdir.join("some.deb"))
    with open(deb_path, 'w') as f:
        f.write("test")
    args = arg_parser.parse_args(["put", "stretch_main", deb_path])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = aptly_ctl.subcommands.put.put(config, args)
    stdout, _ = capsys.readouterr()
    assert stdout == ""
    assert "nothing added or removed" in e._excinfo[1].args[0].lower()


def test_error_on_failed_publish_update(arg_parser, config, monkeypatch, capsys, tmpdir):
    publishes = [
        aptly_api.PublishEndpoint(None, ".", "stretch", "local",
            [{"Component": "main", "Name": "stretch_main"}], ["amd64"], None, None)
            ]

    def _repo_show(*args, **kwargs):
        return aptly_api.Repo("stretch_main", None, None, None)

    def _files_upload(*args, **kwargs):
        return ["stretch_main_123123/aptly_1.3.0+ds1-2_amd64.deb"]

    def _files_delete(*args, **kwargs):
        pass

    def _repo_add_uploaded_file(*args, **kwargs):
        return aptly_api.FileReport([], {"Warnings": [],
            "Added": ["aptly_1.3.0+ds1-2_amd64 added"], "Removed": []})

    def _publish_list(*args, **kwargs):
        return publishes

    def _publish_update(*args, **kwargs):
        raise aptly_api.AptlyAPIException("Internal server error", status_code=500)

    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "show", _repo_show)
    monkeypatch.setattr(aptly_api.parts.files.FilesAPISection, "upload", _files_upload)
    monkeypatch.setattr(aptly_api.parts.files.FilesAPISection, "delete", _files_delete)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "add_uploaded_file",
            _repo_add_uploaded_file)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "list", _publish_list)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "update", _publish_update)
    deb_path = str(tmpdir.join("aptly_1.3.0+ds1-2_amd64.deb"))
    with open(deb_path, 'w') as f:
        f.write("test")
    args = arg_parser.parse_args(["put", "stretch_main", deb_path])
    with pytest.raises(aptly_ctl.exceptions.AptlyCtlError) as e:
        rc = aptly_ctl.subcommands.put.put(config, args)
    stdout, _ = capsys.readouterr()
    ref = aptly_ctl.utils.PackageRef(stdout.strip(" \"'\n\t\r"))
    assert ref.repo == "stretch_main"
    assert len(ref.hash) > 0
    assert "some publishes fail to update" in e._excinfo[1].args[0].lower()


def test_put_multiple_packages(arg_parser, config, monkeypatch, capsys, tmpdir):
    publishes = [
        aptly_api.PublishEndpoint(None, ".", "stretch", "local",
            [{"Component": "main", "Name": "stretch_main"}], ["amd64"], None, None)
            ]

    def _repo_show(*args, **kwargs):
        return aptly_api.Repo("stretch_main", None, None, None)

    def _files_upload(*args, **kwargs):
        return [
                "stretch_main_123123/aptly_1.3.0+ds1-2_amd64.deb",
                "stretch_main_123123/python3.6_3.6.7-1_amd64.deb"
                ]

    def _files_delete(*args, **kwargs):
        pass

    def _repo_add_uploaded_file(*args, **kwargs):
        return aptly_api.FileReport(
                failed_files=[],
                report={
                    "Warnings": [],
                    "Added": ["aptly_1.3.0+ds1-2_amd64 added", "python3.6_3.6.7-1_amd64 added"],
                    "Removed": []
                    }
                )

    def _publish_list(*args, **kwargs):
        return publishes

    def _publish_update(*args, **kwargs):
        return publishes[0]

    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "show", _repo_show)
    monkeypatch.setattr(aptly_api.parts.files.FilesAPISection, "upload", _files_upload)
    monkeypatch.setattr(aptly_api.parts.files.FilesAPISection, "delete", _files_delete)
    monkeypatch.setattr(aptly_api.parts.repos.ReposAPISection, "add_uploaded_file",
            _repo_add_uploaded_file)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "list", _publish_list)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "update", _publish_update)
    deb1_path = str(tmpdir.join("aptly_1.3.0+ds1-2_amd64.deb"))
    deb2_path = str(tmpdir.join("python3.6_3.6.7-1_amd64.deb"))
    for p in [ deb1_path, deb2_path ]:
        with open(p, 'w') as f:
            f.write("test " + p)
    args = arg_parser.parse_args(["put", "stretch_main", deb1_path, deb2_path])
    rc = aptly_ctl.subcommands.put.put(config, args)
    assert rc == 0
    stdout, _ = capsys.readouterr()
    refs = stdout.split("\n")
    assert len(refs) == 3 # 3 newlines, 3d element is empty string
    ref0 = aptly_ctl.utils.PackageRef(refs[0].strip(" \"'\n\t\r"))
    ref1 = aptly_ctl.utils.PackageRef(refs[1].strip(" \"'\n\t\r"))
    assert len(ref0.repo) > 0
    assert len(ref0.hash) > 0
    assert len(ref1.repo) > 0
    assert len(ref1.hash) > 0
