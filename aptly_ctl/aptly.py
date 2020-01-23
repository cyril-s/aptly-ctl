import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import product
from typing import Tuple, Union, Iterable, List, Optional, Dict
from aptly_api import Client, AptlyAPIException
from aptly_ctl.exceptions import (
    AptlyCtlError,
    RepoNotFoundError,
    InvalidOperationError,
    SnapshotNotFoundError,
)
from aptly_ctl.types import Package, Repo, Snapshot

logger = logging.getLogger(__name__)


class Aptly:
    """Aptly API client with more convenient commands"""

    def __init__(self, url: str, max_workers: int = 10) -> None:
        self.aptly = Client(url)
        self.max_workers = max_workers

    def repo_show(self, name: str) -> Repo:
        """
        Returns aptly_ctl.types.Repo representing local repo 'name' or
        raises AtplyCtlError if such local repo does not exist

        Arguments:
            name -- local repo name
        """
        try:
            show_result = self.aptly.repos.show(name)
        except AptlyAPIException as exc:
            if exc.status_code == 404:
                raise RepoNotFoundError(name)
            raise
        else:
            return Repo.from_aptly_api(show_result)

    def repo_list(self) -> Tuple[Repo, ...]:
        """Returns all local repos as tuple of aptly_ctl.types.Repo"""
        return tuple(map(Repo.from_aptly_api, self.aptly.repos.list()))

    def repo_create(
        self, name: str, comment: str = None, dist: str = None, comp: str = None
    ) -> Repo:
        """
        Creates new repo 'name'. Raises AtplyCtlEror if such repo exists

        Arguments:
            name -- local repo name

        Keyword arguments:
            comment -- comment for local repo
            dist -- default distribution. Usefull when creating publishes
            comp -- default component. Usefull when creating publishes
        """
        try:
            create_result = self.aptly.repos.create(name, comment, dist, comp)
        except AptlyAPIException as exc:
            # repo with this name already exists
            if exc.status_code == 400:
                raise InvalidOperationError(str(exc))
            raise
        else:
            logger.info("Created repo %s", create_result)
            return Repo.from_aptly_api(create_result)

    def repo_edit(
        self, name: str, comment: str = None, dist: str = None, comp: str = None
    ) -> Repo:
        """
        Modifies local repo named 'name'. Raises AptlyCtlError if there is no
        repo named 'name' or no fields to modify were supplied

        Arguments:
            name -- local repo name

        Keyword arguments:
            comment -- comment for local repo
            dist -- default distribution. Usefull when creating publishes
            comp -- default component. Usefull when creating publishes
        """
        try:
            edit_result = self.aptly.repos.edit(name, comment, dist, comp)
        except AptlyAPIException as exc:
            # 0 - at least one of comment, dist, comp required
            # 404 - repo with this name not found
            if exc.status_code == 0:
                raise InvalidOperationError(str(exc))
            if exc.status_code == 404:
                raise RepoNotFoundError(name)
            raise
        else:
            logger.info("Edited repo: %s", edit_result)
            return Repo.from_aptly_api(edit_result)

    def repo_delete(self, name: str, force: bool = False) -> None:
        """
        Delete repo named 'name'. Raises AptlyCtlError if there is no such repo
        or when trying to delete repo pointed by snapshot with force=False

        Arguments:
            name -- local repo name

        Keyword arguments:
            force -- delete local repo even if it's pointed by a snapshot
        """
        try:
            self.aptly.repos.delete(name, force)
        except AptlyAPIException as exc:
            # 404 - repo with this name not found
            # 409 - repository can’t be dropped
            if exc.status_code == 404:
                raise RepoNotFoundError(name)
            if exc.status_code == 409:
                raise InvalidOperationError(str(exc))
            raise
        else:
            logger.info("Deleted repo %s", name)

    def repo_search(
        self,
        repo: Union[str, Repo],
        query: str = None,
        with_depls: bool = False,
        details: bool = False,
    ) -> Repo:
        """
        Search packages in local repo using query and return
        aptly_ctl.types.Repo with packages attribute set to frozen set of
        aptly_ctl.types.Package or empty frozenset if nothing was found.

        Arguments:
            repo -- local repo name as string or aptly_ctl.types.Repo.
                    In latter case aptly_ctl.types.Repo instance is reused
                    without making extra roundtrip

        Keyword arguments:
            query -- optional search query. By default lists all packages
            with_depls -- if True, also returns dependencies of packages
                          matched in query
            details -- fill in 'fields' attribute of returned
                       aptly_ctl.types.Package instances

        Raises AptlyCtlError is query is bad or repo does not exist.
        """
        # reuse Repo instance instead of extra roundtrip
        if not isinstance(repo, Repo):
            repo = self.repo_show(repo)
        try:
            pkgs = self.aptly.repos.search_packages(
                repo.name, query, with_depls, details
            )
        except AptlyAPIException as exc:
            emsg = exc.args[0]
            if exc.status_code == 400 and "parsing failed:" in emsg.lower():
                _, _, fail_desc = emsg.partition(":")
                raise InvalidOperationError(
                    'Bad query "{}":{}'.format(query, fail_desc)
                )
            if exc.status_code == 404:
                raise RepoNotFoundError(repo.name)
            raise
        return repo._replace(
            packages=frozenset(Package.from_aptly_api(pkg) for pkg in pkgs)
        )

    def snapshot_show(self, name: str) -> Snapshot:
        """
        Returns aptly_ctl.types.Snapshot representing snapshot 'name' or
        raises AtplyCtlError if such snapshot does not exist

        Arguments:
            name -- snapshot name
        """
        try:
            snapshot = self.aptly.snapshots.show(name)
        except AptlyAPIException as exc:
            if exc.status_code == 404:
                raise SnapshotNotFoundError(name)
            raise
        else:
            return Snapshot.from_aptly_api(snapshot)

    def snapshot_list(self) -> Tuple[Snapshot, ...]:
        """Returns all snapshots as tuple of aptly_ctl.types.Snapshot"""
        return tuple(map(Snapshot.from_aptly_api, self.aptly.snapshots.list()))

    def snapshot_create(
        self, repo_name: str, snapshot_name: str, description: str = None
    ) -> Snapshot:
        """
        Create snapshot from local repo

        Arguments:
            repo_name -- local repo name to snapshot
            snapshot_name -- new snapshot name

        Keyword arguments:
            description -- optional human-readable description string
        """
        try:
            snapshot = self.aptly.snapshots.create_from_repo(
                repo_name, snapshot_name, description
            )
        except AptlyAPIException as exc:
            # 400 - snapshot already exists
            # 404 - repo with this name not found
            if exc.status_code == 400:
                raise InvalidOperationError(str(exc))
            if exc.status_code == 404:
                raise RepoNotFoundError(repo_name)
            raise
        else:
            logger.info(
                "Created snapshot '%s' from local repo '%s'", snapshot_name, repo_name
            )
            return Snapshot.from_aptly_api(snapshot)

    def snapshot_edit(
        self, name: str, new_name: str = None, new_description: str = None
    ) -> Snapshot:
        """
        Modifies snapshot named 'name'. Raises AptlyCtlError if there is no
        snapshot named 'name' or no fields to modify were supplied

        Arguments:
            name -- snapshot name

        Keyword arguments:
            new_name -- rename snapshot to this name
            new_description -- set description to this
        """
        try:
            snapshot = self.aptly.snapshots.update(name, new_name, new_description)
        except AptlyAPIException as exc:
            # 0 - at least one of new_name, new_description required
            # 404 - snapshot with this name not found
            # 409 - snapshot with named new_name already exists
            if exc.status_code in [0, 409]:
                raise InvalidOperationError(str(exc))
            if exc.status_code == 404:
                raise RepoNotFoundError(name)
            raise
        else:
            logger.info("Edited snapshot %s: %s", name, snapshot)
            return Snapshot.from_aptly_api(snapshot)

    def snapshot_delete(self, name: str, force: bool = False) -> None:
        """
        Delete snapshot named 'name'. Raises AptlyCtlError if there is no such
        snapshot or when trying to delete snapshot that has references to it
        with force=False

        Arguments:
            name -- snapshot name

        Keyword arguments:
            force -- delete snapshot even if it's referenced
        """
        try:
            self.aptly.snapshots.delete(name, force)
        except AptlyAPIException as exc:
            # 404 - snapshot with this name not found
            # 409 - snapshot can’t be dropped
            if exc.status_code == 404:
                raise SnapshotNotFoundError(name)
            if exc.status_code == 409:
                raise InvalidOperationError(str(exc))
            raise
        else:
            logger.info("Deleted snapshot %s", name)

    def snapshot_search(
        self,
        snapshot: Union[str, Snapshot],
        query: str = None,
        with_depls: bool = False,
        details: bool = False,
    ) -> Snapshot:
        """
        Search packages in snapshot using query and return
        aptly_ctl.types.Snapshot with packages attribute set to frozen set of
        aptly_ctl.types.Package or empty frozenset if nothing was found.

        Arguments:
            snapshot -- snapshot name as string or aptly_ctl.types.Snapshot.
                        In latter case aptly_ctl.types.Snapshot instance is
                        reused without making extra roundtrip

        Keyword arguments:
            query -- optional search query. By default lists all packages
            with_depls -- if True, also returns dependencies of packages
                          matched in query
            details -- fill in 'fields' attribute of returned
                       aptly_ctl.types.Package instances

        Raises AptlyCtlError is query is bad or snapshot does not exist.
        """
        # reuse Snapshot instance instead of extra roundtrip
        if not isinstance(snapshot, Snapshot):
            snapshot = self.snapshot_show(snapshot)
        try:
            pkgs = self.aptly.snapshots.list_packages(
                snapshot.name, query, with_depls, details
            )
        except AptlyAPIException as exc:
            emsg = exc.args[0]
            if exc.status_code == 400 and "parsing failed:" in emsg.lower():
                _, _, fail_desc = emsg.partition(":")
                raise InvalidOperationError(
                    'Bad query "{}":{}'.format(query, fail_desc)
                )
            if exc.status_code == 404:  # snapshot not found
                raise SnapshotNotFoundError(snapshot.name)
            raise
        return snapshot._replace(
            packages=frozenset(Package.from_aptly_api(pkg) for pkg in pkgs)
        )

    def snapshot_diff(
        self, snap1: str, snap2: str
    ) -> List[Tuple[Optional[Package], Optional[Package]]]:
        """
        Show diff between 2 snapshots
        """
        out = []
        for line in self.aptly.snapshots.diff(snap1, snap2):
            left = Package.from_key(line["Left"]) if line["Left"] else None
            right = Package.from_key(line["Right"]) if line["Right"] else None
            out.append((left, right))
        return out

    def search(
        self,
        repos: Iterable = tuple(),
        snapshots: Iterable = tuple(),
        queries: Iterable = None,
        with_deps: bool = False,
        details: bool = False,
    ) -> Tuple[List[Union[Repo, Snapshot]], List[Exception]]:
        """
        Search list of queries in aptly local repos in parallel and return
        tuple of aptly_ctl.types.Repo's list with found packages and list of
        exceptions encountered during search

        Keyword arguments:
            repos -- local repos names as list of strings or '*' to search in
                     in every local repo
            snapshots -- snapshots names as list of strings or '*' to search in
                         every snapshot
            queries -- list of search queries. By default lists all packages
            with_depls -- if True, also returns dependencies of packages
                          matched in query
            details -- fill in 'fields' attribute of returned
                       aptly_ctl.types.Package instances

        If repos and snapshots are both not supplied, this is the same as
        repos='*', snapshots='*'

        Returns: tuple (result, erros), where
            result -- list of aptly_ctl.types.Repo and aptly_ctl.types.Snapshot
                instances with packages attribute set to the query result
            errors -- list of exceptions occured during search
        """
        queries = tuple(queries) if queries else (None,)
        if not (repos or snapshots):
            repos = self.repo_list()
            snapshots = self.snapshot_list()
        else:
            if repos == "*":
                repos = self.repo_list()
            if snapshots == "*":
                snapshots = self.snapshot_list()

        results = {}  # type: Dict[Union[Repo, Snapshot], set]
        futures = []
        errors = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            try:
                for repo, query in product(repos, queries):
                    futures.append(
                        exe.submit(self.repo_search, repo, query, with_deps, details)
                    )
                for snapshot, query in product(snapshots, queries):
                    futures.append(
                        exe.submit(
                            self.snapshot_search, snapshot, query, with_deps, details
                        )
                    )
                for future in as_completed(futures, 300):
                    try:
                        container = future.result()
                        if container.packages:
                            key = container._replace(packages=frozenset())
                            results.setdefault(key, set()).update(container.packages)
                    except Exception as exc:
                        errors.append(exc)
            except KeyboardInterrupt:
                # NOTE we cannot cancel requests that are hanging on open()
                # so thread pool's context manager will hang on shutdown()
                # untill these requests timeout. Timeout is set in aptly client
                # class constructor and defaults to 60 seconds
                # Second SIGINT crushes everything though
                logger.warning("Received SIGINT. Trying to abort requests...")
                for future in futures:
                    future.cancel()
                raise
        result = []
        for container, pkgs in results.items():
            result.append(container._replace(packages=frozenset(pkgs)))
        return (result, errors)

    def put(
        self,
        local_repos: Iterable[str],
        packages: Iterable[str],
        force_replace: bool = False,
    ) -> Tuple[List[Repo], List[Repo], List[Exception]]:
        """
        Upload packages from local filesystem to aptly server,
        put them into local_repos

        Arguments:
            local_repos -- list of names of local repos to put packages in
            packages -- list of package file names to upload

        Keyworad arguments:
            force_replace -- when True remove packages conflicting with package being added

        Returns: tuple (added, failed, errors), where
            added -- list of instances of aptly_ctl.types.Repo with
                packages attribute set to frozenset of aptly_ctl.types.Package
                instances that were successfully added to a local repo
            failed -- list of instances of aptly_ctl.types.Repo with
                packages attribute set to frozenset of aptly_ctl.types.Package
                instances that were not added to a local repo
            errors -- list of exceptions raised during packages addition
        """
        timestamp = datetime.utcnow().timestamp()
        # os.getpid just in case 2 instances launched at the same time
        directory = "aptly_ctl_put_{:.0f}_{}".format(timestamp, os.getpid())
        repos_to_put = [self.repo_show(name) for name in set(local_repos)]

        try:
            pkgs = tuple(Package.from_file(pkg) for pkg in packages)
        except OSError as exc:
            raise AptlyCtlError("Failed to load package: {}".format(exc))

        def worker(
            repo: Repo, pkgs: Iterable[Package], directory: str, force_replace: bool
        ) -> Tuple[Repo, Repo]:
            addition = self.aptly.repos.add_uploaded_file(
                repo.name,
                directory,
                remove_processed_files=False,
                force_replace=force_replace,
            )
            for file in addition.failed_files:
                logger.warning("Failed to add file %s to repo %s", file, repo.name)
            for msg in addition.report["Warnings"] + addition.report["Removed"]:
                logger.warning(msg)
            # example Added msg "python3-wheel_0.30.0-0.2_all added"
            added = [p.split()[0] for p in addition.report["Added"]]
            added_pkgs, failed_pkgs = [], []
            for pkg in pkgs:
                try:
                    added.remove(pkg.dir_ref)
                except ValueError:
                    failed_pkgs.append(pkg)
                else:
                    added_pkgs.append(pkg)
            # FIXME aptly_ctl.types.Package.from_file implementation is incomplete
            # and will allow such errors to occur
            if added:
                logger.warning(
                    "Output is incomplete! These packages %s %s",
                    added,
                    "were added but omitted in output",
                )
            return (
                repo._replace(packages=frozenset(added_pkgs)),
                repo._replace(packages=frozenset(failed_pkgs)),
            )

        logger.info('Uploading the packages to directory "%s"', directory)
        futures, added, failed, errors = [], [], [], []
        try:
            self.aptly.files.upload(directory, *packages)
            with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
                try:
                    for repo in repos_to_put:
                        futures.append(
                            exe.submit(worker, repo, pkgs, directory, force_replace)
                        )
                    for future in as_completed(futures, 300):
                        try:
                            result = future.result()
                            if result[0].packages:
                                added.append(result[0])
                            if result[1].packages:
                                failed.append(result[1])
                        except Exception as exc:
                            errors.append(exc)
                except KeyboardInterrupt:
                    # NOTE we cannot cancel requests that are hanging on open()
                    # so thread pool's context manager will hang on shutdown()
                    # untill these requests timeout. Timeout is set in aptly client
                    # class constructor and defaults to 60 seconds
                    # Second SIGINT crushes everything though
                    logger.warning("Received SIGINT. Trying to abort requests...")
                    for future in futures:
                        future.cancel()
                    raise
        finally:
            logger.info("Deleting directory %s", directory)
            self.aptly.files.delete(path=directory)

        return (added, failed, errors)

    def remove(self, *repos: Repo) -> List[Tuple[Repo, RepoNotFoundError]]:
        """
        Deletes packages from local repo

        Arguments:
            *repos -- aptly_ctl.types.Repo instances where packages from
                     'packages' field are to be deleted

        Returns list of tuples for every repo for which package removal failed.
        The first item in a tuple is an aptly_ctl.types.Repo and the second is
        exception with description of failure
        """
        fails = []
        for repo in repos:
            if not repo.packages:
                continue
            try:
                self.aptly.repos.delete_packages_by_key(
                    repo.name, *[pkg.key for pkg in repo.packages]
                )
            except AptlyAPIException as exc:
                if exc.status_code == 404:
                    fails.append((repo, RepoNotFoundError(repo.name)))
                else:
                    raise
        return fails
