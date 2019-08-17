import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from aptly_api import Client, AptlyAPIException
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.types import Package, Repo

logger = logging.getLogger(__name__)


class Aptly:
    """Aptly API client with more convenient commands"""

    def __init__(self, url, max_workers=10):
        self.aptly = Client(url)
        self.max_workers = max_workers

    def repo_show(self, name):
        """
        Returns aptly_ctl.types.Repo representing local repo 'name' or
        raises AtplyCtlError such local repo does not exist

        Arguments:
            name -- local repo name
        """
        try:
            show_result = self.aptly.repos.show(name)
        except AptlyAPIException as exc:
            # repo with this name doesn't exists
            if exc.status_code == 404:
                raise AptlyCtlError(exc) from exc
            raise
        else:
            return Repo.fromAptlyApi(show_result)

    def repo_list(self):
        """Returns all local repos as tuple of aptly_ctl.types.Repo"""
        return tuple(map(Repo.fromAptlyApi, self.aptly.repos.list()))

    def repo_create(self, name, comment=None, dist=None, comp=None):
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
                raise AptlyCtlError(exc) from exc
            raise
        else:
            logger.info("Created repo %s", create_result)
            return Repo.fromAptlyApi(create_result)

    def repo_edit(self, name, comment=None, dist=None, comp=None):
        """
        Modifies local repo named 'name'. Raises AptlyCtlError if there is no
        repo named 'name' or no fieldst modify were supplied

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
            if exc.status_code in [0, 404]:
                raise AptlyCtlError(exc) from exc
            raise
        else:
            logger.info("Edited repo: %s", edit_result)
            return Repo.fromAptlyApi(edit_result)

    def repo_delete(self, name, force=False):
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
            if exc.status_code in [404, 409]:
                raise AptlyCtlError(exc) from exc
            raise
        else:
            logger.info("Deleted repo %s", name)

    def repo_search(self, repo, query="", with_depls=False, details=False):
        """
        Search packages in local repo using query and return
        aptly_ctl.types.Repo with packages attribute set to frozen set of
        aptly_ctl.types.Package or empty frozenset if nothing was found.

        Arguments:
            repo -- local repo name as string or aptly_ctl.types.Repo

        Keyword arguments:
            query -- search query. Default is "" and means 'get everything'
            with_depls -- if True, also returns dependencies of packages
                          matched in query
            details -- fill in 'fields' attribute of returned
                       aptly_ctl.types.Package instances

        Raises AptlyCtlError is query is bad or repo does not exist.
        """
        try:
            repo = self.repo_show(repo.name)
        except AttributeError:
            repo = self.repo_show(repo)
        try:
            result = self.aptly.repos.search_packages(
                repo.name, query, with_depls, details)
        except AptlyAPIException as exc:
            emsg = exc.args[0]
            if exc.status_code == 400 and "parsing failed:" in emsg.lower():
                _, _, fail_desc = emsg.partition(":")
                raise AptlyCtlError(
                    'Bad query "{}":{}'.format(query, fail_desc))
            elif exc.status_code == 404: # repo not found
                raise AptlyCtlError(exc) from exc
            raise
        return repo._replace(
            packages=frozenset(Package.fromAptlyApi(pkg) for pkg in result))

    def search(self, repos=None, queries=None, with_deps=False, details=False):
        """
        Search list of queries in aptly local repos in parallel and return
        tuple of aptly_ctl.types.Repo's list with found packages and list of
        exceptions encountered during search

        Keyword arguments:
            repos -- local repos names as list of strings. Default None means
                     search every local repo
            queries -- search query. Default is "" and means 'get everything'
            with_depls -- if True, also returns dependencies of packages
                          matched in query
            details -- fill in 'fields' attribute of returned
                       aptly_ctl.types.Package instances
        """
        queries = tuple(queries) if queries else ("",)
        if not repos:
            repos = self.repo_list()

        futures, results, errors = [], {}, []
        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            try:
                for repo in repos:
                    for query in queries:
                        futures.append(exe.submit(
                            self.repo_search,
                            repo,
                            query,
                            with_deps,
                            details,
                            ))
                for future in as_completed(futures, 300):
                    try:
                        repo = future.result()
                        if repo.packages:
                            key = repo._replace(packages=None)
                            results.setdefault(key, set()).update(repo.packages)
                    except Exception as exc:
                        errors.append(exc)
            except KeyboardInterrupt:
                #NOTE we cannot cancel requests that are hanging on open()
                # so thread pool's context manager will hang on shutdown()
                # untill these requests timeout. Timeout is set in aptly client
                # class constructor and defaults to 60 seconds
                # Second SIGINT crushes everything though
                logger.warning("Received SIGINT. Trying to abort requests...")
                for future in futures:
                    future.cancel()
                raise

        return (
            [r._replace(packages=frozenset(p)) for r, p in results.items()],
            errors
            )

    def put(self, local_repos, packages, force_replace=False):
        """
        Upload packages from local filesystem to aptly server,
        put them into local_repos
        """
        timestamp = datetime.utcnow().timestamp()
        # os.getpid just in case 2 instances launched at the same time
        directory = "aptly_ctl_put_{:.0f}_{}".format(timestamp, os.getpid())
        repos_to_put = [self.repo_show(name) for name in set(local_repos)]

        try:
            pkgs = tuple(Package.fromFile(pkg) for pkg in packages)
        except OSError as exc:
            raise AptlyCtlError("Failed to load package: {}".format(exc))

        def worker(repo, pkgs, directory, force_replace):
            addition = self.aptly.repos.add_uploaded_file(
                repo.name,
                directory,
                remove_processed_files=False,
                force_replace=force_replace
                )
            for file in addition.failed_files:
                logger.warning("Failed to add file %s to repo %s",
                               file, repo.name)
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
            #FIXME aptly_ctl.types.Package.fromFile implementation is incomplete
            # and will allow such errors to occur
            if added:
                logger.warning("Output is incomplete! These packages %s %s",
                               added, "were added but omitted in output")
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
                        futures.append(exe.submit(
                            worker, repo, pkgs, directory, force_replace))
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
                    #NOTE we cannot cancel requests that are hanging on open()
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
