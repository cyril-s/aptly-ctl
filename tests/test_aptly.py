import pytest  # type: ignore
import random
from typing import Iterator, Sequence
import os.path
import aptly_ctl.aptly
from datetime import datetime
from aptly_ctl.aptly import Client
from aptly_ctl.aptly import Repo, Snapshot, Source, Package, PackageFileInfo
from aptly_ctl.exceptions import AptlyApiError
from aptly_ctl.debian import Version


def rand(prefix: str = "") -> str:
    return "{}{}".format(prefix, random.randrange(100000))


# new Debian package, version 2.0.
# size 4703664 bytes: control archive=1668 bytes.
#    2697 bytes,    25 lines      control
#     397 bytes,     6 lines      md5sums
# Package: aptly
# Version: 1.3.0+ds1-2.2~deb10u1
# Architecture: amd64
# Maintainer: Sebastien Delafond <seb@debian.org>
# Installed-Size: 19022
# Depends: bzip2, xz-utils, gnupg1, gpgv1, libc6 (>= 2.3.2)
# Suggests: graphviz
# Built-Using: golang-1.11 (= 1.11.6-1), golang-github-aleksi-pointer (= 1.0.0+git20180620.11deede-1), golang-github-awalterschulze-gographviz (= 2.0+git20180607.da5c847-1), golang-github-aws-aws-sdk-go (= 1.16.18+dfsg-1), golang-github-disposaboy-jsonconfigreader (= 0.0~git20171218.5ea4d0d-2), golang-github-gin-contrib-sse (= 0.0~git20170109.0.22d885f-1), golang-github-gin-gonic-gin (= 1.3.0+dfsg1-3), golang-github-golang-snappy (= 0.0+git20160529.d9eb7a3-3), golang-github-jlaffaye-ftp (= 0.0~git20170707.0.a05056b-1), golang-github-jmespath-go-jmespath (= 0.2.2-2), golang-github-kjk-lzma (= 1.0.0-5), golang-github-mattn-go-isatty (= 0.0.4-1), golang-github-mattn-go-runewidth (= 0.0.4-1), golang-github-mattn-go-shellwords (= 1.0.3-1), golang-github-mkrautz-goar (= 0.0~git20150919.282caa8-1), golang-github-mxk-go-flowrate (= 0.0~git20140419.0.cca7078-1), golang-github-ncw-swift (= 0.0~git20180327.b2a7479-2), golang-github-pborman-uuid (= 1.1-1), golang-github-pkg-errors (= 0.8.1-1), golang-github-smira-commander (= 0.0~git20140515.f408b00-1), golang-github-smira-flag (= 0.0~git20170926.695ea5e-1), golang-github-smira-go-aws-auth (= 0.0~git20160320.0070896-1), golang-github-smira-go-ftp-protocol (= 0.0~git20140829.066b75c-2), golang-github-smira-go-xz (= 0.0~git20150414.0c531f0-2), golang-github-ugorji-go-codec (= 1.1.1-1), golang-github-wsxiaoys-terminal (= 0.0~git20160513.0.0940f3f-1), golang-go.crypto (= 1:0.0~git20181203.505ab14-1), golang-golang-x-sys (= 0.0~git20181228.9a3f9b0-1), golang-goleveldb (= 0.0~git20170725.0.b89cc31-2), golang-gopkg-cheggaaa-pb.v1 (= 1.0.25-1), golang-gopkg-go-playground-validator.v8 (= 8.18.1-1), golang-gopkg-h2non-filetype.v1 (= 1.0.5+ds1-2), golang-goprotobuf (= 1.2.0-1), golang-yaml.v2 (= 2.2.2-1)
# Section: utils
# Priority: optional
# Homepage: http://www.aptly.info
# Description: Swiss army knife for Debian repository management - main package
#  It offers several features making it easy to manage Debian package
#  repositories:
#  .
#   - make mirrors of remote Debian/Ubuntu repositories, limiting by
#     components/architectures
#   - take snapshots of mirrors at any point in time, fixing state of
#     repository at some moment of time
#   - publish snapshot as Debian repository, ready to be consumed by apt
#   - controlled update of one or more packages in snapshot from upstream
#     mirror, tracking dependencies
#   - merge two or more snapshots into one
#  .
#  This is the main package, it contains the aptly command-line utility.
class TestPackage:
    def test_from_file(self):
        expected_file_info = PackageFileInfo(
            filename="aptly_1.3.0+ds1-2.2~deb10u1_amd64.deb",
            path="tests/packages/db/aptly_1.3.0+ds1-2.2~deb10u1_amd64.deb",  # stripped full path
            origpath="tests/packages/db/aptly_1.3.0+ds1-2.2~deb10u1_amd64.deb",
            size=4703664,
            md5="7d2fd2ee7f3ad630ea4f92fcdadd36be",
            sha1="b72c6203a93b3f276f8a3613d61f880a96dacc7d",
            sha256="a165d40d93a6aba4e008b4bc5933a1f2d11e72c85b49fd4cfce4f01905755f80",
        )

        expected_fields = {
            "Filename": "aptly_1.3.0+ds1-2.2~deb10u1_amd64.deb",
            "FilesHash": "89e028161a5a6661",
            "Key": "Pamd64 aptly 1.3.0+ds1-2.2~deb10u1 89e028161a5a6661",
            "MD5sum": "7d2fd2ee7f3ad630ea4f92fcdadd36be",
            "SHA1": "b72c6203a93b3f276f8a3613d61f880a96dacc7d",
            "SHA256": "a165d40d93a6aba4e008b4bc5933a1f2d11e72c85b49fd4cfce4f01905755f80",
            "SHA512": "82aa58eb18f8247b7a03143d1945fe9c845ed335ae4e3583ee1153e3e9d55670dadcdbfca01ce735806e7ef65445e7727b39546355e00269ceda443a66cd2d44",
            "ShortKey": "Pamd64 aptly 1.3.0+ds1-2.2~deb10u1",
            "Size": "4703664",
            "Package": "aptly",
            "Version": "1.3.0+ds1-2.2~deb10u1",
            "Architecture": "amd64",
            "Maintainer": "Sebastien Delafond <seb@debian.org>",
            "Installed-Size": "19022",
            "Depends": "bzip2, xz-utils, gnupg1, gpgv1, libc6 (>= 2.3.2)",
            "Suggests": "graphviz",
            "Built-Using": "golang-1.11 (= 1.11.6-1), golang-github-aleksi-pointer (= 1.0.0+git20180620.11deede-1), golang-github-awalterschulze-gographviz (= 2.0+git20180607.da5c847-1), golang-github-aws-aws-sdk-go (= 1.16.18+dfsg-1), golang-github-disposaboy-jsonconfigreader (= 0.0~git20171218.5ea4d0d-2), golang-github-gin-contrib-sse (= 0.0~git20170109.0.22d885f-1), golang-github-gin-gonic-gin (= 1.3.0+dfsg1-3), golang-github-golang-snappy (= 0.0+git20160529.d9eb7a3-3), golang-github-jlaffaye-ftp (= 0.0~git20170707.0.a05056b-1), golang-github-jmespath-go-jmespath (= 0.2.2-2), golang-github-kjk-lzma (= 1.0.0-5), golang-github-mattn-go-isatty (= 0.0.4-1), golang-github-mattn-go-runewidth (= 0.0.4-1), golang-github-mattn-go-shellwords (= 1.0.3-1), golang-github-mkrautz-goar (= 0.0~git20150919.282caa8-1), golang-github-mxk-go-flowrate (= 0.0~git20140419.0.cca7078-1), golang-github-ncw-swift (= 0.0~git20180327.b2a7479-2), golang-github-pborman-uuid (= 1.1-1), golang-github-pkg-errors (= 0.8.1-1), golang-github-smira-commander (= 0.0~git20140515.f408b00-1), golang-github-smira-flag (= 0.0~git20170926.695ea5e-1), golang-github-smira-go-aws-auth (= 0.0~git20160320.0070896-1), golang-github-smira-go-ftp-protocol (= 0.0~git20140829.066b75c-2), golang-github-smira-go-xz (= 0.0~git20150414.0c531f0-2), golang-github-ugorji-go-codec (= 1.1.1-1), golang-github-wsxiaoys-terminal (= 0.0~git20160513.0.0940f3f-1), golang-go.crypto (= 1:0.0~git20181203.505ab14-1), golang-golang-x-sys (= 0.0~git20181228.9a3f9b0-1), golang-goleveldb (= 0.0~git20170725.0.b89cc31-2), golang-gopkg-cheggaaa-pb.v1 (= 1.0.25-1), golang-gopkg-go-playground-validator.v8 (= 8.18.1-1), golang-gopkg-h2non-filetype.v1 (= 1.0.5+ds1-2), golang-goprotobuf (= 1.2.0-1), golang-yaml.v2 (= 2.2.2-1)",
            "Section": "utils",
            "Priority": "optional",
            "Homepage": "http://www.aptly.info",
            "Description": """ Swiss army knife for Debian repository management - main package
 It offers several features making it easy to manage Debian package
 repositories:
 .
  - make mirrors of remote Debian/Ubuntu repositories, limiting by
    components/architectures
  - take snapshots of mirrors at any point in time, fixing state of
    repository at some moment of time
  - publish snapshot as Debian repository, ready to be consumed by apt
  - controlled update of one or more packages in snapshot from upstream
    mirror, tracking dependencies
  - merge two or more snapshots into one
 .
 This is the main package, it contains the aptly command-line utility.
""",
        }
        pkg = Package.from_file(
            "tests/packages/db/aptly_1.3.0+ds1-2.2~deb10u1_amd64.deb"
        )
        assert pkg.name == "aptly"
        assert pkg.version == Version("1.3.0+ds1-2.2~deb10u1")
        assert pkg.arch == "amd64"
        assert pkg.prefix == ""
        assert pkg.files_hash == "89e028161a5a6661"
        assert pkg.file._replace(path="") == expected_file_info._replace(path="")
        assert pkg.file.path.endswith(expected_file_info.path)
        assert pkg.fields == expected_fields


class TestAptlyClient:
    @pytest.fixture
    def aptly(self) -> Iterator[aptly_ctl.aptly.Client]:
        url = "http://localhost:8090/"
        sig_cfg = aptly_ctl.aptly.SigningConfig(
            skip=False,
            gpgkey="DC3CFE1DD8562BB86BF3845A4E15F887476CCCE0",
            passphrase_file="/home/aptly/gpg_pass",
        )
        aptly = aptly_ctl.aptly.Client(url, default_signing_config=sig_cfg)
        yield aptly
        for publish in aptly.publish_list():
            aptly.publish_drop(publish, force=True)
        for repo in aptly.repo_list():
            aptly.repo_delete(repo.name, force=True)
        for snapshot in aptly.snapshot_list():
            aptly.snapshot_delete(snapshot.name, force=True)
        for d in aptly.files_list_dirs():
            aptly.files_delete_dir(d)

    def test_files_upload(self, aptly: Client, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        resp = aptly.files_upload(files, directory)
        assert set(resp) == set(
            os.path.join(directory, pkg.file.filename) for pkg in packages_simple
        )

    def test_files_list_dirs(self, aptly: Client, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        assert [directory] == aptly.files_list_dirs()

    def test_files_list(self, aptly: Client, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        resp = aptly.files_list(directory)
        assert set(resp) == set(pkg.file.filename for pkg in packages_simple)

    def test_files_delete_file(self, aptly: Client, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        deleted_file = os.path.basename(files[0])
        directory = rand("dir")
        aptly.files_upload(files, directory)
        aptly.files_delete_file(directory, deleted_file)
        assert deleted_file not in aptly.files_list(directory)

    def test_files_delete_dir(self, aptly: Client, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        aptly.files_delete_dir(directory)
        assert directory not in aptly.files_list_dirs()

    def test_repo_create_and_show(self, aptly: Client):
        for kwargs in [
            {"name": rand("test")},
            {"name": rand("test"), "comment": "comment"},
            {
                "name": rand("test"),
                "comment": "comment",
                "default_distribution": "buster",
            },
            {
                "name": rand("test"),
                "comment": "comment",
                "default_distribution": "buster",
                "default_component": "contrib",
            },
        ]:
            repo = Repo(**kwargs)
            assert aptly.repo_create(**kwargs) == repo
            assert aptly.repo_show(kwargs["name"]) == repo

    def test_repo_list(self, aptly: Client):
        repos = set()
        assert not aptly.repo_list()
        repos.add(aptly.repo_create(rand("test")))
        assert set(aptly.repo_list()) == repos
        repos.add(aptly.repo_create(rand("test"), "comment"))
        assert set(aptly.repo_list()) == repos

    def test_repo_edit(self, aptly: Client):
        src = Repo(rand("repo"))
        tgt = src._replace(comment="comment")
        assert aptly.repo_create(src.name) == src
        assert aptly.repo_edit(tgt.name, tgt.comment) == tgt

    def test_repo_delete(self, aptly: Aptly):
        name = rand("test")
        aptly.repo_create(name)
        aptly.repo_show(name)
        aptly.repo_delete(name)
        with pytest.raises(AptlyApiError, match=r"local repo.*not found"):
            aptly.repo_show(name)

    def test_repo_delete_force(self, aptly: Client):
        repo = aptly.repo_create(rand("repo"))
        aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        with pytest.raises(AptlyApiError, match="unable to drop.*has snapshots"):
            aptly.repo_delete(repo.name)
        aptly.repo_delete(repo.name, True)

    def test_repo_add_packages(self, aptly: Client, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        repo = aptly.repo_create(rand("repo"))
        report = aptly.repo_add_packages(repo.name, directory)
        assert not report.failed
        assert not report.warnings
        assert not report.removed
        assert set(report.added) == set(pkg.dir_ref for pkg in packages_simple)

    def test_repo_add_packages_one_file(
        self, aptly: Client, packages_simple: Sequence[Package]
    ):
        pkg = list(packages_simple)[0]
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath], directory)
        repo = aptly.repo_create(rand("repo"))
        report = aptly.repo_add_packages(repo.name, directory, pkg.file.filename)
        assert not report.failed
        assert not report.warnings
        assert not report.removed
        assert len(report.added) == 1
        assert report.added[0] == pkg.dir_ref

    def test_repo_add_packages_conflict(
        self, aptly: Client, packages_conflict: Sequence[Package]
    ):
        assert len(packages_conflict) == 2
        pkgs = list(packages_conflict)
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in pkgs], directory)
        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory, pkgs[0].file.filename)
        report = aptly.repo_add_packages(repo.name, directory, pkgs[1].file.filename)
        assert len(report.failed) == 1
        assert pkgs[1].file.filename in report.failed[0]
        assert len(report.warnings) == 1
        assert pkgs[1].dir_ref in report.warnings[0]
        assert not report.removed
        assert not report.added

    def test_repo_add_packages_conflict_force_replace(
        self, aptly: Client, packages_conflict: Sequence[Package]
    ):
        assert len(packages_conflict) == 2
        pkgs = list(packages_conflict)
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in pkgs], directory)
        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory, pkgs[0].file.filename)
        report = aptly.repo_add_packages(
            repo.name, directory, pkgs[1].file.filename, force_replace=True
        )
        assert not report.failed
        assert not report.warnings
        assert len(report.removed) == 1
        assert pkgs[0].dir_ref in report.removed[0]
        assert len(report.added) == 1
        assert report.added[0] == pkgs[1].dir_ref

    def test_repo_search(self, aptly: Client, packages_simple: Sequence[Package]):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        expected_pkgs = [
            pkg._replace(file=None, fields=None) for pkg in packages_simple
        ]
        found_pkgs = aptly.repo_search(repo.name)
        assert sorted(expected_pkgs) == sorted(found_pkgs)

    def test_repo_search_details(
        self, aptly: Client, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        expected_pkgs = [pkg._replace(file=None) for pkg in packages_simple]
        found_pkgs = aptly.repo_search(repo.name, details=True)
        expected_pkgs.sort()
        found_pkgs.sort()
        assert len(expected_pkgs) == len(found_pkgs)
        for found_pkg, expexted_pkg in zip(found_pkgs, expected_pkgs):
            assert found_pkg.fields == expexted_pkg.fields
            assert found_pkg == expexted_pkg

    def test_repo_search_with_query(
        self, aptly: Client, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        expected_pkgs = [
            pkg._replace(file=None, fields=None)
            for pkg in packages_simple
            if pkg.name == "aptly"
        ]
        found_pkgs = aptly.repo_search(repo.name, "aptly")
        assert sorted(expected_pkgs) == sorted(found_pkgs)

    def test_repo_add_packages_by_key(
        self, aptly: Client, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        src_repo = aptly.repo_create(rand("repo"))
        tgt_repo = aptly.repo_create(rand("repo"))

        aptly.repo_add_packages(src_repo.name, directory)
        resp_repo = aptly.repo_add_packages_by_key(
            tgt_repo.name, [pkg.key for pkg in packages_simple]
        )
        assert resp_repo == tgt_repo

        expected_pkgs = [
            pkg._replace(file=None, fields=None) for pkg in packages_simple
        ]
        found_pkgs = aptly.repo_search(tgt_repo.name)
        assert sorted(expected_pkgs) == sorted(found_pkgs)

    def test_repo_add_packages_by_key_conflict(
        self, aptly: Client, packages_conflict: Sequence[Package]
    ):
        assert len(packages_conflict) == 2
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_conflict], directory)

        src_repo1 = aptly.repo_create(rand("repo"))
        src_repo2 = aptly.repo_create(rand("repo"))
        tgt_repo = aptly.repo_create(rand("repo"))

        aptly.repo_add_packages(
            src_repo1.name, directory, packages_conflict[0].file.filename
        )
        aptly.repo_add_packages(
            src_repo2.name, directory, packages_conflict[1].file.filename
        )

        with pytest.raises(AptlyApiError, match=r"^conflict in package .*"):
            aptly.repo_add_packages_by_key(
                tgt_repo.name, [pkg.key for pkg in packages_conflict]
            )

        found_pkgs = aptly.repo_search(tgt_repo.name)
        assert not found_pkgs

    def test_repo_delete_packages_by_key(
        self, aptly: Client, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        resp_repo = aptly.repo_delete_packages_by_key(
            repo.name, [pkg.key for pkg in packages_simple]
        )
        assert resp_repo == repo

        found_pkgs = aptly.repo_search(repo.name)
        assert not found_pkgs

    def test_snapshot_create_from_repo(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        snap_name = rand("snap")
        snap = aptly.snapshot_create_from_repo(repo.name, snap_name, "test description")
        assert snap.name == snap_name
        assert snap.description == "test description"
        assert isinstance(snap.created_at, datetime)

    def test_snapshot_create_from_package_keys(
        self, aptly: Client, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        snap = aptly.snapshot_create_from_package_keys(
            rand("snap"), [pkg.key for pkg in packages_simple]
        )
        assert not snap.description
        assert isinstance(snap.created_at, datetime)

        found_pkgs = aptly.snapshot_search(snap.name)
        expected_pkgs = [
            pkg._replace(file=None, fields=None) for pkg in packages_simple
        ]
        assert sorted(found_pkgs) == sorted(expected_pkgs)

    def test_snapshot_show(self, aptly: Client):
        snap = aptly.snapshot_create_from_package_keys(rand("snap"), [])
        assert snap == aptly.snapshot_show(snap.name)

    def test_snapshot_list(self, aptly: Client):
        snaps = []
        for _ in range(5):
            snaps.append(aptly.snapshot_create_from_package_keys(rand("snap"), []))
        assert sorted(snaps) == sorted(aptly.snapshot_list())

    def test_snapshot_edit(self, aptly: Client):
        snap = aptly.snapshot_create_from_package_keys(rand("snap"), [])
        modified_snap = aptly.snapshot_edit(snap.name)
        assert modified_snap == snap
        modified_snap = aptly.snapshot_edit(snap.name, new_description="test desc")
        assert modified_snap.description == "test desc"
        assert aptly.snapshot_show(modified_snap.name).description == "test desc"
        new_name = rand("new_snap")
        modified_snap = aptly.snapshot_edit(snap.name, new_name=new_name)
        assert modified_snap.name == new_name
        assert aptly.snapshot_show(modified_snap.name).name == new_name

    def test_snapshot_delete(self, aptly: Client):
        snap = aptly.snapshot_create_from_package_keys(rand("snap"), [])
        aptly.snapshot_delete(snap.name)
        with pytest.raises(AptlyApiError, match="snapshot.*not found"):
            aptly.snapshot_show(snap.name)

    def test_snapshot_delete_force(self, aptly: Client):
        snap1 = aptly.snapshot_create_from_package_keys(rand("snap"), [])
        aptly.snapshot_create_from_package_keys(
            rand("snap"), [], source_snapshots=[snap1.name]
        )
        with pytest.raises(
            AptlyApiError,
            match="won't delete snapshot that was used as source for other snapshots",
        ):
            aptly.snapshot_delete(snap1.name)
        aptly.snapshot_delete(snap1.name, True)

    def test_snapshot_search(self, aptly: Client, packages_simple: Sequence[Package]):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"))

        expected_pkgs = [
            pkg._replace(file=None, fields=None) for pkg in packages_simple
        ]
        found_pkgs = aptly.snapshot_search(snap.name)
        assert sorted(expected_pkgs) == sorted(found_pkgs)

    def test_snapshot_diff(self, aptly: Client, packages_simple: Sequence[Package]):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        snap1 = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        aptly.repo_add_packages(repo.name, directory)
        snap2 = aptly.snapshot_create_from_repo(repo.name, rand("snap"))

        diff = aptly.snapshot_diff(snap1.name, snap2.name)
        assert all([line[0] is None for line in diff])
        expected_pkgs = [
            pkg._replace(file=None, fields=None) for pkg in packages_simple
        ]
        assert sorted([line[1] for line in diff]) == sorted(expected_pkgs)

    def test_publish_create_from_local_repo(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            distribution="stretch",
            architectures=["amd64"],
        )
        assert pub.full_prefix == "."
        assert pub.source_kind == "local"
        assert sorted(pub.sources) == sorted(sources)
        assert pub.distribution == "stretch"

    def test_publish_create_from_snapshot(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        sources = [Source(snap.name, "main")]
        pub = aptly.publish_create(
            source_kind="snapshot",
            sources=sources,
            distribution="stretch",
            architectures=["amd64"],
        )
        assert pub.full_prefix == "."
        assert pub.source_kind == "snapshot"
        assert sorted(pub.sources) == sorted(sources)
        assert pub.distribution == "stretch"

    def test_publish_create_with_prefix(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            prefix="debian",
            distribution="stretch",
            architectures=["amd64"],
        )
        assert pub.full_prefix == "debian"
        assert pub.source_kind == "local"
        assert sorted(pub.sources) == sorted(sources)
        assert pub.distribution == "stretch"

    def test_publish_list(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            distribution="stretch",
            architectures=["amd64"],
        )
        pub_list = aptly.publish_list()
        assert len(pub_list) == 1
        assert pub_list[0] == pub

    def test_publish_drop(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            distribution="stretch",
            architectures=["amd64"],
        )
        aptly.publish_drop(pub)
        pub_list = aptly.publish_list()
        assert len(pub_list) == 0

    def test_publish_drop_str_args(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            distribution="stretch",
            architectures=["amd64"],
        )
        aptly.publish_drop(
            storage=pub.storage, prefix=pub.prefix, distribution=pub.distribution
        )
        pub_list = aptly.publish_list()
        assert len(pub_list) == 0

    def test_publish_update_from_local_repo(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            distribution="buster",
            architectures=["amd64"],
        )
        updated_pub = aptly.publish_update(pub)
        assert updated_pub.prefix == "."
        assert updated_pub.source_kind == "local"
        assert sorted(updated_pub.sources) == sorted(sources)

    def test_publish_update_from_local_repo_str_args(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo.name, "main")]
        pub = aptly.publish_create(
            source_kind="local",
            sources=sources,
            distribution="buster",
            architectures=["amd64"],
        )
        updated_pub = aptly.publish_update(
            storage=pub.storage,
            prefix=pub.prefix,
            distribution=pub.distribution,
            acquire_by_hash=pub.acquire_by_hash,
        )
        assert updated_pub.prefix == "."
        assert updated_pub.source_kind == "local"
        assert sorted(updated_pub.sources) == sorted(sources)

    def test_publish_update_switch_snapshot(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap1_"))
        sources = [Source(snap.name, "main")]
        pub = aptly.publish_create(
            source_kind="snapshot",
            sources=sources,
            distribution="buster",
            architectures=["amd64"],
        )

        snap_new = aptly.snapshot_create_from_repo(repo.name, rand("snap2_"))
        sources_new = [Source(snap_new.name, "main")]
        pub_new = pub._replace(sources=sources_new)
        updated_pub = aptly.publish_update(pub_new)
        assert updated_pub.prefix == "."
        assert updated_pub.source_kind == "snapshot"
        assert sorted(updated_pub.sources) == sorted(sources_new)

    def test_publish_update_switch_snapshot_str_args(self, aptly: Client):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap1_"))
        sources = [Source(snap.name, "main")]
        pub = aptly.publish_create(
            source_kind="snapshot",
            sources=sources,
            distribution="buster",
            architectures=["amd64"],
        )

        snap_new = aptly.snapshot_create_from_repo(repo.name, rand("snap2_"))
        sources_new = [Source(snap_new.name, "main")]
        updated_pub = aptly.publish_update(
            storage=pub.storage,
            prefix=pub.prefix,
            distribution=pub.distribution,
            snapshots=sources_new,
            acquire_by_hash=pub.acquire_by_hash,
        )
        assert updated_pub.prefix == "."
        assert updated_pub.source_kind == "snapshot"
        assert sorted(updated_pub.sources) == sorted(sources_new)

    def test_package_show(self, aptly: Client, packages_simple: Sequence[Package]):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)

        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)

        for pkg in packages_simple:
            showed_pkg = aptly.package_show(pkg.key)
            assert showed_pkg.fields == pkg.fields
            assert showed_pkg == pkg._replace(file=None)

    def test_version(self, aptly: Client):
        version = aptly.version()
        assert isinstance(version, str)

    ###########################################################################################
    @pytest.mark.skip
    def test_put(self, aptly: Client, packages_simple):
        repos = set()
        for _ in range(2):
            repos.add(aptly.repo_create(rand("test")))
        added, failed, errors = aptly.put(
            [repo.name for repo in repos],
            [pkg.file.origpath for pkg in packages_simple],
        )
        assert len(added) == 2
        assert len(failed) == 0
        assert len(errors) == 0
        assert repos == set(repo._replace(packages=frozenset()) for repo in added)
        for repo in added:
            assert repo.packages == frozenset(packages_simple)

    @pytest.mark.skip
    def test_put_conflict_error(self, aptly: Client, packages_conflict):
        pkgs = [pkg.file.origpath for pkg in packages_conflict]
        repo = aptly.repo_create(rand("repo"))
        added, failed, errors = aptly.put([repo.name], pkgs[:1])
        assert len(added) == 1
        assert not failed
        assert not errors
        added, failed, errors = aptly.put([repo.name], pkgs[1:])
        assert not added
        assert len(failed) == 1
        assert not errors

    @pytest.mark.skip
    def test_put_force_replace(self, aptly: Client, packages_conflict):
        pkgs = [pkg.file.origpath for pkg in packages_conflict]
        repo = aptly.repo_create(rand("repo"))
        added, failed, errors = aptly.put([repo.name], pkgs[:1])
        assert len(added) == 1
        assert not failed
        assert not errors
        added, failed, errors = aptly.put([repo.name], pkgs[1:], force_replace=True)
        assert len(added) == 1
        assert not failed
        assert not errors

    @pytest.mark.skip
    def test_search(self, aptly: Client, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        snapshot = aptly.snapshot_create_from_repo(repo.name, rand("test"))
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        expected = [
            repo._replace(packages=expected_pkgs),
            snapshot._replace(packages=expected_pkgs),
        ]

        result, errors = aptly.search([repo, snapshot])
        assert len(result) == 2
        assert len(errors) == 0
        assert set(result) == set(expected)

    @pytest.mark.skip
    def test_search_no_snapshot_error(self, aptly: Client, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        expected = [
            repo._replace(packages=expected_pkgs),
        ]

        result, errors = aptly.search([repo, Snapshot(rand("snap"))])
        assert len(result) == 1
        assert len(errors) == 1
        assert set(result) == set(expected)
        assert isinstance(errors[0], aptly_ctl.exceptions.SnapshotNotFoundError)

    @pytest.mark.skip
    def test_remove(self, aptly: Client, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        expected = aptly._search(repo, query="!aptly")
        to_delete = aptly._search(repo, query="aptly")
        errors = aptly.remove(to_delete)
        assert len(errors) == 0
        remaining = aptly._search(repo)
        assert remaining == expected

    @pytest.mark.skip
    def test_remove_fail(self, aptly: Client, packages_simple):
        repo = Repo("test", packages=frozenset(packages_simple))
        errors = aptly.remove(repo)
        assert len(errors) == 1
        assert isinstance(errors[0][1], aptly_ctl.exceptions.RepoNotFoundError)

    @pytest.mark.skip
    def test_snapshot_create_from_snapshot(self, aptly: Client, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        snap1 = aptly.snapshot_create_from_repo(repo.name, rand("snap"),)
        snap2 = aptly.snapshot_create_from_snapshots(rand("snap"), [snap1])
        snap2 = aptly._search(snap2)
        assert snap2.packages == expected_pkgs

    @pytest.mark.skip
    def test_snapshot_create_from_snapshot_no_source(self, aptly: Client):
        snap = Snapshot(rand("snap"))
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly.snapshot_create_from_snapshots(rand("snap"), [snap])
