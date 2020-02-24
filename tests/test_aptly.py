import pytest  # type: ignore
import random
from typing import Iterator, Sequence
import os.path
import aptly_ctl.aptly
from aptly_ctl.aptly import Aptly
from aptly_ctl.aptly import Repo, Snapshot, Publish, Source, Package
import aptly_ctl.exceptions


def rand(prefix: str = "") -> str:
    return "{}{}".format(prefix, random.randrange(100000))


class TestAptly:
    @pytest.fixture
    def aptly(self) -> Iterator[aptly_ctl.aptly.Aptly]:
        url = "http://localhost:8090/"
        sig_cfg = aptly_ctl.aptly.SigningConfig(
            skip=False,
            gpgkey="DC3CFE1DD8562BB86BF3845A4E15F887476CCCE0",
            passphrase_file="/home/aptly/gpg_pass",
        )
        aptly = aptly_ctl.aptly.Aptly(url, default_signing_config=sig_cfg)
        yield aptly
        for publish in aptly.publish_list():
            aptly.publish_drop(publish, force=True)
        for repo in aptly.repo_list():
            aptly.repo_delete(repo.name, force=True)
        for snapshot in aptly.snapshot_list():
            aptly.snapshot_delete(snapshot.name, force=True)
        for d in aptly.files_list_dirs():
            aptly.files_delete_dir(d)

    def test_files_upload(self, aptly: Aptly, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        resp = aptly.files_upload(files, directory)
        assert set(resp) == set(
            os.path.join(directory, pkg.file.filename) for pkg in packages_simple
        )

    def test_files_list_dirs(self, aptly: Aptly, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        assert [directory] == aptly.files_list_dirs()

    def test_files_list(self, aptly: Aptly, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        resp = aptly.files_list(directory)
        assert set(resp) == set(pkg.file.filename for pkg in packages_simple)

    def test_files_delete_file(self, aptly: Aptly, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        deleted_file = os.path.basename(files[0])
        directory = rand("dir")
        aptly.files_upload(files, directory)
        aptly.files_delete_file(directory, deleted_file)
        assert deleted_file not in aptly.files_list(directory)

    def test_files_delete_dir(self, aptly: Aptly, packages_simple: Sequence[Package]):
        files = [pkg.file.origpath for pkg in packages_simple]
        directory = rand("dir")
        aptly.files_upload(files, directory)
        aptly.files_delete_dir(directory)
        assert directory not in aptly.files_list_dirs()

    def test_repo_create_and_show(self, aptly: Aptly):
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

    def test_repo_list(self, aptly: Aptly):
        repos = set()
        assert not aptly.repo_list()
        repos.add(aptly.repo_create(rand("test")))
        assert set(aptly.repo_list()) == repos
        repos.add(aptly.repo_create(rand("test"), "comment"))
        assert set(aptly.repo_list()) == repos

    def test_repo_edit(self, aptly: Aptly):
        src = Repo(rand("repo"))
        tgt = src._replace(comment="comment")
        assert aptly.repo_create(src.name) == src
        assert aptly.repo_edit(tgt.name, tgt.comment) == tgt

    def test_repo_delete(self, aptly: aptly_ctl.aptly.Aptly):
        name = rand("test")
        aptly.repo_create(name)
        aptly.repo_show(name)
        aptly.repo_delete(name)
        with pytest.raises(aptly_ctl.exceptions.AptlyApiError):
            aptly.repo_show(name)

    def test_repo_add_packages(self, aptly: Aptly, packages_simple: Sequence[Package]):
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
        self, aptly: Aptly, packages_simple: Sequence[Package]
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
        self, aptly: Aptly, packages_conflict: Sequence[Package]
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
        self, aptly: Aptly, packages_conflict: Sequence[Package]
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

    def test_repo_add_packages_by_key(
        self, aptly: Aptly, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)
        src_repo = aptly.repo_create(rand("repo"))
        tgt_repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(src_repo.name, directory)
        resp = aptly.repo_add_packages_by_key(
            tgt_repo.name, [pkg.key for pkg in packages_simple]
        )
        assert resp == tgt_repo

    @pytest.mark.xfail
    def test_repo_add_packages_by_key_conflict(
        self, aptly: Aptly, packages_conflict: Sequence[Package]
    ):
        assert len(packages_conflict) == 2
        directory = rand("dir")
        pkgs = list(packages_conflict)
        aptly.files_upload([pkg.file.origpath for pkg in pkgs], directory)
        src_repo1 = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(src_repo1.name, directory, pkgs[0].file.filename)
        src_repo2 = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(src_repo2.name, directory, pkgs[1].file.filename)
        tgt_repo = aptly.repo_create(rand("repo"))
        resp = aptly.repo_add_packages_by_key(tgt_repo.name, [pkg.key for pkg in pkgs])
        assert resp == tgt_repo

    def test_repo_delete_packages_by_key(
        self, aptly: Aptly, packages_simple: Sequence[Package]
    ):
        directory = rand("dir")
        aptly.files_upload([pkg.file.origpath for pkg in packages_simple], directory)
        repo = aptly.repo_create(rand("repo"))
        aptly.repo_add_packages(repo.name, directory)
        resp = aptly.repo_delete_packages_by_key(
            repo.name, [pkg.key for pkg in packages_simple]
        )
        assert resp == repo

    def test_snapshot_show_no_snapshot_error(test, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly.snapshot_show(rand("test"))

    def test_snapshot_create(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        expexted_snapshot = Snapshot(repo.name, "description", None, frozenset())
        created_snapshot = aptly.snapshot_create_from_repo(
            repo.name, expexted_snapshot.name, expexted_snapshot.description,
        )
        assert expexted_snapshot == created_snapshot._replace(created_at=None)
        shown_snapshot = aptly.snapshot_show(created_snapshot.name)
        assert expexted_snapshot == shown_snapshot._replace(created_at=None)

    def test_snapshot_create_no_repo_error(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.snapshot_create_from_repo(rand("repo"), rand("snap"))

    def test_snapshot_create_same_name_error(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        args = (repo.name, rand("snap"), "description")
        aptly.snapshot_create_from_repo(*args)
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.snapshot_create_from_repo(*args)

    def test_snapshot_edit(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        name = rand("orig_snap")
        orig_args = (name, "description")
        edited_agrs = (rand("new_snap"), "new description")
        expected_snapshot = Snapshot(
            *edited_agrs, created_at=None, packages=frozenset()
        )
        aptly.snapshot_create_from_repo(repo.name, *orig_args)
        edited_snapshot = aptly.snapshot_edit(name, *edited_agrs)
        assert expected_snapshot == edited_snapshot._replace(created_at=None)

    def test_snapshot_edit_no_snapshot_error(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.snapshot_edit(rand("test"), new_description="new desc")

    def test_snapshot_edit_same_snapshot_name_error(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("repo"))
        snap1_name = rand("snap1")
        _ = aptly.snapshot_create_from_repo(repo.name, snap1_name)
        snap2 = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.snapshot_edit(snap2.name, new_name=snap1_name)

    def test_snapshot_delete(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        aptly.snapshot_show(snap.name)
        aptly.snapshot_delete(snap.name)
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly.snapshot_show(snap.name)

    def test_snapshot_delete_no_snapshot_error(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly.snapshot_delete(rand("test"))

    def test_repo_delete_without_force_error(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("repo"))
        _ = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.repo_delete(repo.name)

    def test_repo_delete_force(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("repo"))
        _ = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        aptly.repo_delete(repo.name, force=True)

    def test_snapshot_delete_without_force_error(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"),)
        _ = aptly.snapshot_create_from_snapshots(rand("snap"), [snap])
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.snapshot_delete(snap.name)

    def test_snapshot_delete_force(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"),)
        _ = aptly.snapshot_create_from_snapshots(rand("snap"), [snap])
        aptly.snapshot_delete(snap.name, force=True)
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly.snapshot_show(snap.name)

    def test_put(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
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

    def test_put_no_repo(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
        repos = [rand("test")]
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.put(repos, [pkg.file.origpath for pkg in packages_simple])

    def test_put_conflict_error(self, aptly: aptly_ctl.aptly.Aptly, packages_conflict):
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

    def test_put_force_replace(self, aptly: aptly_ctl.aptly.Aptly, packages_conflict):
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

    def test_repo_search(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        searched_repo = aptly._search(repo)
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        assert repo._replace(packages=expected_pkgs) == searched_repo

    def test_repo_search_no_repo(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly._search(Repo(rand("test")))

    def test_repo_search_bad_query(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly._search(repo, query="Name (")

    def test_snapshot_search(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        snapshot = aptly.snapshot_create_from_repo(repo.name, rand("test"))
        searched_snapshot = aptly._search(snapshot)
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        assert snapshot._replace(packages=expected_pkgs) == searched_snapshot

    def test_snapshot_search_no_snapshot(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly._search(Snapshot(rand("test")))

    def test_snapshot_search_bad_query(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        snapshot = aptly.snapshot_create_from_repo(repo.name, rand("test"))
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly._search(snapshot, query="Name (")

    def test_search(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
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

    def test_search_no_snapshot_error(
        self, aptly: aptly_ctl.aptly.Aptly, packages_simple
    ):
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

    def test_remove(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        expected = aptly._search(repo, query="!aptly")
        to_delete = aptly._search(repo, query="aptly")
        errors = aptly.remove(to_delete)
        assert len(errors) == 0
        remaining = aptly._search(repo)
        assert remaining == expected

    def test_remove_fail(self, aptly: aptly_ctl.aptly.Aptly, packages_simple):
        repo = Repo("test", packages=frozenset(packages_simple))
        errors = aptly.remove(repo)
        assert len(errors) == 1
        assert isinstance(errors[0][1], aptly_ctl.exceptions.RepoNotFoundError)

    def test_snapshot_create_from_snapshot(
        self, aptly: aptly_ctl.aptly.Aptly, packages_simple
    ):
        repo = aptly.repo_create(rand("test"))
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        snap1 = aptly.snapshot_create_from_repo(repo.name, rand("snap"),)
        snap2 = aptly.snapshot_create_from_snapshots(rand("snap"), [snap1])
        snap2 = aptly._search(snap2)
        assert snap2.packages == expected_pkgs

    def test_snapshot_create_from_snapshot_no_source(
        self, aptly: aptly_ctl.aptly.Aptly
    ):
        snap = Snapshot(rand("snap"))
        with pytest.raises(aptly_ctl.exceptions.SnapshotNotFoundError):
            aptly.snapshot_create_from_snapshots(rand("snap"), [snap])

    def test_snapshot_create_from_snapshot_same_name_error(
        self, aptly: aptly_ctl.aptly.Aptly
    ):
        snap_name = rand("snap")
        repo = aptly.repo_create(rand("test"))
        snap1 = aptly.snapshot_create_from_repo(repo.name, snap_name)
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.snapshot_create_from_snapshots(snap_name, [snap1])

    def test_snapshot_create_from_packages(
        self, aptly: aptly_ctl.aptly.Aptly, packages_simple
    ):
        repo = aptly.repo_create(rand("test"))
        expected_pkgs = frozenset(pkg._replace(file=None) for pkg in packages_simple)
        aptly.put([repo.name], [pkg.file.origpath for pkg in packages_simple])
        snap = aptly.snapshot_create_from_packages(rand("snap"), packages_simple)
        search_result = aptly._search(snap)
        assert search_result.packages == expected_pkgs

    def test_publish_create_from_local_repo(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo, "main")]
        pub_to_create = Publish.new(
            sources, distribution="stretch", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        assert pub.full_prefix == "."
        assert pub.source_kind == "local"
        assert pub.sources == frozenset(sources)
        assert pub.distribution == "stretch"

    def test_publish_create_from_snapshot(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        sources = [Source(snap._replace(description="", created_at=None), "main")]
        pub_to_create = Publish.new(
            sources, distribution="stretch", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        assert pub.full_prefix == "."
        assert pub.source_kind == "snapshot"
        assert pub.sources == frozenset(sources)
        assert pub.distribution == "stretch"

    def test_publish_create_with_prefix(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo, "main")]
        pub_to_create = Publish.new(
            sources, prefix="debian", distribution="stretch", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        assert pub.full_prefix == "debian"
        assert pub.source_kind == "local"
        assert pub.sources == frozenset(sources)
        assert pub.distribution == "stretch"

    def test_publish_list(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo, "main")]
        pub_to_create = Publish.new(
            sources, distribution="stretch", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        pub_list = aptly.publish_list()
        assert len(pub_list) == 1
        assert pub_list[0] == pub

    def test_publish_drop(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo, "main")]
        pub_to_create = Publish.new(
            sources, distribution="stretch", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        aptly.publish_drop(pub)
        pub_list = aptly.publish_list()
        assert len(pub_list) == 0

    def test_publish_drop_str_args(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo, "main")]
        pub_to_create = Publish.new(
            sources, distribution="stretch", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        aptly.publish_drop(
            storage=pub.storage, prefix=pub.prefix, distribution=pub.distribution
        )
        pub_list = aptly.publish_list()
        assert len(pub_list) == 0

    def test_publish_update_from_local_repo(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        sources = [Source(repo, "main")]
        pub_to_create = Publish.new(
            sources, distribution="buster", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)
        updated_pub = aptly.publish_update(pub)
        assert updated_pub.prefix == "."
        assert updated_pub.source_kind == "local"
        assert updated_pub.sources == frozenset(sources)

    def test_publish_update_switch_snapshot(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("test"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap1_"))
        sources = [Source(snap, "main")]
        pub_to_create = Publish.new(
            sources, distribution="buster", architectures=["amd64"]
        )
        pub = aptly.publish_create(pub_to_create)

        snap_new = aptly.snapshot_create_from_repo(repo.name, rand("snap2_"))
        sources_new = frozenset(
            [Source(snap_new._replace(description="", created_at=None), "main")]
        )
        pub_new = pub._replace(sources=sources_new)
        updated_pub = aptly.publish_update(pub_new)
        assert updated_pub.prefix == "."
        assert updated_pub.source_kind == "snapshot"
        assert updated_pub.sources == sources_new


class TestPublish:
    def test_new(self):
        sources_repos = [Source(Repo("repo1"), "comp1"), Source(Repo("repo2"), "comp2")]
        sources_snaps = [
            Source(Snapshot("snap1"), "comp1"),
            Source(Snapshot("snap1"), "comp2"),
        ]
        p_repos = Publish.new(sources_repos)
        p_snaps = Publish.new(sources_snaps)
        assert p_repos.source_kind == "local"
        assert p_snaps.source_kind == "snapshot"
        assert p_repos.sources == frozenset(sources_repos)
        assert p_snaps.sources == frozenset(sources_snaps)
        for p in [p_repos, p_snaps]:
            assert p.storage == ""
            assert p.prefix == ""
            assert p.distribution == ""
            assert p.full_prefix == "."
            assert p.full_prefix_escaped == ":."

    def test_new_prefix(self):
        sources = [Source(Repo("repo1"))]
        for storage, prefix, full, escaped in [
            (None, None, ".", ":."),
            (None, "debian", "debian", "debian"),
            ("s3", "debian", "s3:debian", "s3:debian"),
            ("s3", "pkg/debian_new", "s3:pkg/debian_new", "s3:pkg_debian__new"),
        ]:
            p = Publish.new(sources, storage=storage, prefix=prefix)
            assert p.full_prefix == full
            assert p.full_prefix_escaped == escaped

    def test_new_mixed_sources_error(self):
        sources = [Source(Repo("repo"), "comp1"), Source(Snapshot("snap"), "comp2")]
        with pytest.raises(ValueError):
            Publish.new(sources)

    def test_new_invalid_source_error(self):
        sources = [Source("repo", "comp1")]
        with pytest.raises(ValueError):
            Publish.new(sources)

    def test_new_empty_sources_error(self):
        with pytest.raises(ValueError):
            Publish.new([])

    def test_new_invalid_prefix_error(self):
        sources = [Source(Repo("repo1"))]
        with pytest.raises(ValueError):
            Publish.new(sources, prefix="s3:debian")

    def test_api_params(self):
        repo = Repo("repo1")
        sources = [Source(repo, "main")]
        p = Publish.new(
            sources,
            storage="s3",
            prefix="debian",
            distribution="buster",
            architectures=["amd64"],
            label="label",
            origin="origin",
            not_automatic="yes",
            but_automatic_upgrades=True,
            acquire_by_hash=True,
        )
        params = p.api_params
        assert params == {
            "SourceKind": "local",
            "Sources": [{"Name": repo.name, "Component": "main"}],
            "Distribution": "buster",
            "Architectures": ["amd64"],
            "Label": "label",
            "Origin": "origin",
            "NotAutomatic": "yes",
            "ButAutomaticUpgrades": "yes",
            "AcquireByHash": True,
        }

    def test_from_api_response(self):
        pass
