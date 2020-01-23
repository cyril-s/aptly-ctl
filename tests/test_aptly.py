import pytest
import random
from datetime import datetime
import aptly_ctl.aptly
from aptly_ctl.types import Repo, Package, Snapshot
import aptly_ctl.exceptions


def rand(prefix=""):
    return "{}{}".format(prefix, random.randrange(100000))


class TestAptly:
    @pytest.fixture
    def aptly(self):
        url = "http://localhost:8090/"
        aptly = aptly_ctl.aptly.Aptly(url)
        yield aptly
        try:
            for repo in aptly.repo_list():
                try:
                    aptly.repo_delete(repo.name, force=True)
                except Exception as e:
                    print("Failed to cleanup repos: {}".format(e))
        except Exception as e:
            print("Failed to cleanup repos: {}".format(e))
        try:
            for snapshot in aptly.snapshot_list():
                try:
                    aptly.snapshot_delete(snapshot.name, force=True)
                except Exception as e:
                    print("Failed to cleanup snapshots: {}".format(e))
        except Exception as e:
            print("Failed to cleanup snapshots: {}".format(e))

    def test_repo_show_no_repo_error(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.repo_show(rand("test"))

    def test_repo_create(self, aptly: aptly_ctl.aptly.Aptly):
        expexted_repo = Repo(rand("test"), "comment", "sid", "main", frozenset())
        created_repo = aptly.repo_create(
            expexted_repo.name,
            expexted_repo.comment,
            expexted_repo.default_distribution,
            expexted_repo.default_component,
        )
        assert created_repo == expexted_repo
        shown_repo = aptly.repo_show(created_repo.name)
        assert shown_repo == expexted_repo

    def test_repo_create_same_name_error(self, aptly: aptly_ctl.aptly.Aptly):
        args = (rand("test"), "comment", "sid", "main")
        aptly.repo_create(*args)
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.repo_create(*args)

    def test_repo_edit(self, aptly: aptly_ctl.aptly.Aptly):
        name = rand("test")
        orig_args = (name, "comment", "sid", "main")
        edited_agrs = (name, "new comment", "buster", "contrib")
        expected_repo = Repo(*edited_agrs, packages=frozenset())
        aptly.repo_create(*orig_args)
        edited_repo = aptly.repo_edit(*edited_agrs)
        assert edited_repo == expected_repo

    def test_repo_edit_no_repo_error(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.repo_edit(rand("test"), comment="bla")

    def test_repo_delete(self, aptly: aptly_ctl.aptly.Aptly):
        name = rand("test")
        aptly.repo_create(name)
        aptly.repo_show(name)
        aptly.repo_delete(name)
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.repo_show(name)

    def test_repo_delete_no_repo_error(self, aptly: aptly_ctl.aptly.Aptly):
        with pytest.raises(aptly_ctl.exceptions.RepoNotFoundError):
            aptly.repo_delete(rand("test"))

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
        snap1 = aptly.snapshot_create_from_repo(repo.name, snap1_name)
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
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        with pytest.raises(aptly_ctl.exceptions.InvalidOperationError):
            aptly.repo_delete(repo.name)

    def test_repo_delete_force(self, aptly: aptly_ctl.aptly.Aptly):
        repo = aptly.repo_create(rand("repo"))
        snap = aptly.snapshot_create_from_repo(repo.name, rand("snap"))
        aptly.repo_delete(repo.name, force=True)

    # def test_snapshot_delete_without_force_error(self, aptly):
    # def test_snapshot_delete_force(self, aptly):

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

    # def test_put_conflict_error
    # def test_put_force_replace

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
