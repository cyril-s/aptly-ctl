"""This module contains command line entrypoint and functions for corresponding subcommands"""
import argparse
import logging
import re
from typing import (
    Iterable,
    Any,
    List,
    Union,
    Optional,
    Tuple,
    Dict,
    Pattern,
    Container,
    Generator,
    cast,
)
import sys
import os
from datetime import datetime
import string
from enum import Enum
import urllib3.exceptions  # type: ignore # https://github.com/urllib3/urllib3/issues/1897
from urllib3 import Timeout
from aptly_ctl import VERSION
from aptly_ctl.aptly import (
    Client,
    Repo,
    Snapshot,
    Package,
    search,
    PackageFileInfo,
    Publish,
    Source,
    InvalidPackageKey,
)
from aptly_ctl.config import Config, parse_override_dict
from aptly_ctl.debian import Version
from aptly_ctl.exceptions import AptlyCtlError, AptlyApiError
from aptly_ctl.util import print_table, size_pretty

log = logging.getLogger(__name__)

PACKAGE_QUERY_DOC_URL = "https://www.aptly.info/doc/feature/query/"
DEBIAN_POLICY_BUT_AUTOMATIC_UPGRADES_LINK = "https://wiki.debian.org/DebianRepository/Format#NotAutomatic_and_ButAutomaticUpgrades"


def regex(pattern: str) -> re.Pattern:
    """Compile pattern into regex object"""
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise argparse.ArgumentTypeError("Invalid regex '{}': {}".format(pattern, exc))


def str_list(str_list_raw: str) -> List[str]:
    """Convert string elements separated by comas into a list discarding empty strings"""
    return [elem for elem in str_list_raw.split(",") if elem]


def update_dependent_publishes(
    aptly: Client,
    repo_names: Container[str],
    dry_run: bool,
) -> None:
    """Find and update publishes, that were created from local repos, listed in repo_names argument"""
    publishes = set()
    for publish in aptly.publish_list():
        if publish.source_kind != "local":
            continue
        for source in publish.sources:
            if source.name in repo_names:
                publishes.add(publish)

    if not publishes:
        return
    print()

    if dry_run:
        print_table([[str(p)] for p in publishes], ["Publishes to update"])
        return

    updated_publishes = []
    failed_to_updated_publishes = []
    for publish in publishes:
        try:
            updated_publishes.append(aptly.publish_update(publish))
        except AptlyApiError as exc:
            failed_to_updated_publishes.append([str(publish), int(exc.status), exc])

    print_table([[str(p)] for p in updated_publishes], ["Updated publishes"])

    if failed_to_updated_publishes:
        print()
        print_table(
            failed_to_updated_publishes,
            ["Failed to update publishes", "HTTP status code", "Reason"],
        )
        raise AptlyCtlError("Some publishes failed to update")


def version(parser: argparse.ArgumentParser) -> None:
    """configure 'version' subcommand"""

    def action(*, aptly: Client, **_unused: Any) -> None:
        print(aptly.version())

    parser.set_defaults(func=action)


def package_show(parser: argparse.ArgumentParser) -> None:
    """configure 'package show' subcommand"""

    parser.add_argument(
        "keys_or_queries",
        metavar="<package key or query>",
        nargs="+",
        help="package key or query",
    )

    first_fileds = ["Package", "Version", "Architecture"]
    last_fields = ["Description"]
    skip_fields = set(first_fileds) | set(last_fields) | {"Key", "ShortKey"}

    def print_packages(packages: Iterable[Package]) -> None:
        for package in packages:
            if not package.fields:
                raise RuntimeError("package fileds are empty")
            print('"', package.key, '"', sep="")
            for field in first_fileds:
                print("   ", field, ":", package.fields[field])
            for field in sorted(package.fields.keys()):
                if field in skip_fields:
                    continue
                print("   ", field, ":", package.fields[field])
            for field in last_fields:
                print("   ", field, ":", package.fields[field])

    def action(
        *,
        aptly: Client,
        max_workers: int,
        keys_or_queries: Iterable[str],
        **_unused: Any,
    ) -> None:
        keys = []
        queries = []
        for key_or_query in keys_or_queries:
            try:
                Package.from_key(key_or_query)
                keys.append(key_or_query)
            except InvalidPackageKey:
                queries.append(key_or_query)

        pkgs = set()
        err_exit = False
        for key in keys:
            try:
                pkgs.add(aptly.package_show(key))
            except AptlyApiError as exc:
                if exc.status == 404:
                    log.error("Package with key '%s' wasn't found", key)
                    err_exit = True
                    continue
                raise

        if queries:
            result, errors = search(
                aptly,
                queries,
                details=True,
                max_workers=max_workers,
            )
            pkgs.update(package for _, packages in result for package in packages)
            for error in errors:
                log.error(error)
                err_exit = True

        print_packages(pkgs)

        if err_exit:
            raise AptlyCtlError("Some packages were not found")

    parser.set_defaults(func=action)


def package_search(parser: argparse.ArgumentParser) -> None:
    """configure 'package search' subcommand"""
    # pylint: disable=too-many-statements

    parser.add_argument(
        "queries",
        metavar="query",
        nargs="*",
        default=("",),
        help="package queries. Multiple queries are ORed. For query syntax see "
        + PACKAGE_QUERY_DOC_URL,
    )
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="include dependencies when evaluating package query",
    )
    parser.add_argument(
        "-o",
        "--out-columns",
        dest="base_out_columns",
        type=str_list,
        metavar="OUT_COLUMNS",
        default="store_type,store_name,package_name,package_version,package_dir_ref,package_key_quoted",
        help="""output columns. Available columns: store_type, store_name,
        package_name, package_arch, package_version, package_hash,
        package_dir_ref, package_key, package_key_quoted.
        Also every field from output of 'package show' is also available
        (note that they start with a capital letter)"
        """,
    )
    parser.add_argument(
        "-O",
        "--extra-out-columns",
        dest="extra_out_columns",
        type=str_list,
        metavar="EXTRA_OUT_COLUMNS",
        default="",
        help="output columns to append to a default set",
    )
    parser.add_argument(
        "-f",
        "--store-filter",
        metavar="REGEXP",
        type=regex,
        help="Only search packages in repos and snapshots that satisfy filter",
    )
    parser.add_argument(
        "-r",
        "--sort-reverse",
        action="store_true",
        help="sort in descending order",
    )

    parser.add_argument(
        "--no-header",
        action="store_true",
        help="do not print header of the output table",
    )

    def build_out_row(
        cols: Iterable[str], store: Union[Snapshot, Repo], package: Package
    ) -> List[Any]:
        """build a row in a table to be printed"""
        # pylint: disable=too-many-branches
        row: List[Union[str, Version]] = []
        for col in cols:
            if col == "store_type":
                row.append("Snapshot" if isinstance(store, Snapshot) else "Repo")
            elif col == "store_name":
                row.append(store.name)
            elif col == "package_key":
                row.append(package.key)
            elif col == "package_key_quoted":
                row.append('"' + package.key + '"')
            elif col == "package_name":
                row.append(package.name)
            elif col == "package_arch":
                row.append(package.arch)
            elif col == "package_version":
                row.append(package.version)
            elif col == "package_hash":
                row.append(package.files_hash)
            elif col == "package_dir_ref":
                row.append(package.dir_ref)
            elif col == "Installed-Size":
                assert package.fields
                row.append(size_pretty(int(package.fields[col]) * 1024))
            elif col == "Size":
                assert package.fields
                row.append(size_pretty(int(package.fields[col])))
            elif col[0] in string.ascii_uppercase:
                assert package.fields
                try:
                    row.append(package.fields[col])
                except KeyError:
                    raise AptlyCtlError("Unknown output column name: " + col) from None
            else:
                raise AptlyCtlError("Unknown output column name: " + col)
        return row

    def action(
        *,
        aptly: Client,
        queries: Iterable[str],
        with_deps: bool,
        base_out_columns: List[str],
        extra_out_columns: List[str],
        max_workers: int,
        store_filter: Optional[Pattern],
        sort_reverse: bool,
        no_header: bool,
        **_unused: Any,
    ) -> None:
        out_columns = base_out_columns + extra_out_columns
        details = any(col[0] in string.ascii_uppercase for col in out_columns)

        result, errors = search(
            aptly,
            queries,
            with_deps,
            details,
            max_workers=max_workers,
            store_filter=store_filter,
        )
        table = [
            build_out_row(out_columns, store, package)
            for store, packages in result
            for package in packages
        ]
        # sort table by every column from right to left
        for index in range(len(out_columns) - 1, -1, -1):
            # pylint: disable=cell-var-from-loop
            table.sort(key=lambda row: row[index], reverse=sort_reverse)
        if no_header:
            print_table(table)
        else:
            print_table(table, out_columns)
        for error in errors:
            log.error(error)
        if errors:
            raise AptlyCtlError("Package search finished with errors")

    parser.set_defaults(func=action)


def package_remove(parser: argparse.ArgumentParser) -> None:
    """configure 'package remove' subcommand"""
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="just show packages to be removed",
    )
    parser.add_argument(
        "-U",
        "--update-publishes",
        action="store_true",
        help="update dependent publishes",
    )
    parser.add_argument(
        "-f",
        "--repo-filter",
        metavar="REGEXP",
        type=regex,
        help="filter local repos where packages will be removed",
    )
    parser.add_argument(
        "-y",
        "--yes",
        dest="skip_confirm",
        action="store_true",
        help="don't ask for confirmation",
    )
    parser.add_argument(
        "package_queries", nargs="+", metavar="<package_query>", help="package query"
    )

    def action(
        *,
        aptly: Client,
        max_workers: int,
        dry_run: bool,
        update_publishes: bool,
        repo_filter: Optional[Pattern],
        skip_confirm: bool,
        package_queries: List[str],
        **_unused: Any,
    ) -> None:
        result, errors = search(
            aptly,
            package_queries,
            max_workers=max_workers,
            store_filter=repo_filter,
            search_snapshots=False,
        )

        if not result and not errors:
            print("Nothing to remove")
            return

        header = [
            "repo name",
            "package to be removed",
            "package version",
            "package hash",
        ]
        table = [
            [repo.name, package.name, package.version, package.files_hash]
            for repo, packages in result
            for package in packages
        ]
        table.sort()
        print_table(table, header)

        for error in errors:
            log.error(error)
        if errors:
            raise AptlyCtlError("Package search finished with errors")

        if not skip_confirm and not dry_run:
            answer = input("Remove listed packages? [y/N]: ")
            if answer.lower() not in ["y", "yes"]:
                print("Package removal was canceled")
                return

        if not dry_run:
            for repo, packages in result:
                aptly.repo_delete_packages_by_key(repo.name, [p.key for p in packages])

        if update_publishes:
            repo_names = [repo.name for repo, _ in result]
            update_dependent_publishes(aptly, repo_names, dry_run)

    parser.set_defaults(func=action)


def repo_list(parser: argparse.ArgumentParser) -> None:
    """configure 'repo list' subcommand"""

    def action(
        *,
        aptly: Client,
        **_unused: Any,
    ) -> None:
        repos = aptly.repo_list()
        if not repos:
            print("No local repos!")
            return
        header = list(repos[0]._fields)
        table = [list(repo) for repo in sorted(repos)]
        print_table(table, header=header)

    parser.set_defaults(func=action)


def repo_create_or_edit(parser: argparse.ArgumentParser, is_edit: bool) -> None:
    """configure 'repo create' and 'repo edit' subcommands"""
    parser.add_argument("repo_name", metavar="<repo_name>", help="local repo name")
    parser.add_argument(
        "--comment",
        metavar="<repo_comment>",
        dest="repo_comment",
        default="",
        help="comment for local repo",
    )
    parser.add_argument(
        "--dist",
        metavar="<default_distribution>",
        dest="default_distribution",
        default="",
        help="default distribution. When creating publish"
        " from local repo, this attribute is looked up to determine target"
        " distribution for publish if it is not supplied explicitly.",
    )
    parser.add_argument(
        "--comp",
        metavar="<default_component>",
        dest="default_component",
        default="",
        help="default component. When creating publish"
        " from local repo, this attribute is looked up to determine target"
        " component for this repo if it is not supplied explicitly.",
    )

    def action(
        *,
        aptly: Client,
        repo_name: str,
        repo_comment: str,
        default_distribution: str,
        default_component: str,
        **_unused: Any,
    ) -> None:
        if is_edit:
            try:
                repo = aptly.repo_edit(
                    repo_name,
                    repo_comment,
                    default_distribution,
                    default_component,
                )
            except AptlyApiError as exc:
                if exc.status == 404:
                    raise AptlyCtlError(
                        f"Failed to edit local repo '{repo_name}'"
                    ) from exc
                raise
        else:
            try:
                repo = aptly.repo_create(
                    repo_name,
                    repo_comment,
                    default_distribution,
                    default_component,
                )
            except AptlyApiError as exc:
                if exc.status == 400:
                    raise AptlyCtlError(
                        f"Failed to create local repo '{repo_name}'"
                    ) from exc
                raise
        print_table([list(repo)], header=list(repo._fields))

    parser.set_defaults(func=action)


def repo_drop(parser: argparse.ArgumentParser) -> None:
    """configure 'repo drop' subcommand"""
    parser.add_argument("repo_name", metavar="<repo_name>", help="local repo name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="delete local repo even if it's pointed by a snapshot",
    )

    def action(*, aptly: Client, repo_name: str, force: bool, **_unused: Any) -> None:
        try:
            aptly.repo_delete(repo_name, force)
        except AptlyApiError as exc:
            if exc.status in [404, 409]:
                raise AptlyCtlError(f"Failed to delete repo '{repo_name}'") from exc
            raise
        print(f"Deleted repo '{repo_name}'")

    parser.set_defaults(func=action)


def load_packages_dict(
    package_files: List[str],
) -> Dict[str, Tuple[Package, PackageFileInfo]]:
    """load packages from filesystem into dict indexed by package dir_ref"""
    packages: Dict[str, Tuple[Package, PackageFileInfo]] = {}
    for pkg_file in package_files:
        try:
            pkg, file_info = Package.from_file(pkg_file)
        except Exception as exc:
            raise AptlyCtlError(f"Failed to load package '{pkg_file}'") from exc
        if pkg.dir_ref in packages:
            log.error(
                "Package '%s' (%s) conflicts with '%s' (%s)",
                file_info.path,
                pkg.key,
                packages[pkg.dir_ref][1].path,
                packages[pkg.dir_ref][0].key,
            )
        else:
            packages[pkg.dir_ref] = (pkg, file_info)
    return packages


def repo_add(parser: argparse.ArgumentParser) -> None:
    """configure 'repo add' subcommand"""
    parser.add_argument(
        "--force-replace",
        action="store_true",
        help="when adding package that conflicts with existing package, remove existing package",
    )
    parser.add_argument(
        "-U",
        "--update-publishes",
        action="store_true",
        help="update dependent publishes",
    )
    parser.add_argument("repo", metavar="<repo>", help="local repository name")
    parser.add_argument(
        "package_files", metavar="<package>", nargs="+", help="package file"
    )

    def action(
        *,
        aptly: Client,
        force_replace: bool,
        update_publishes: bool,
        repo: str,
        package_files: List[str],
        **_unused: Any,
    ) -> None:
        # os.getpid just in case 2 instances launched at the same time
        directory = f"aptly_ctl_repo_add_{datetime.utcnow():%s}_{os.getpid()}"
        packages = load_packages_dict(package_files)

        log.info("Uploading packages into directory '%s'", directory)
        try:
            table = []
            log.debug("Uploaded files %s", aptly.files_upload(package_files, directory))
            try:
                files_report = aptly.repo_add_packages(
                    repo, directory, force_replace=force_replace
                )
            except AptlyApiError as exc:
                if exc.status == 404:
                    raise AptlyCtlError(
                        f"Failed to upload packages to local repo '{repo}'"
                    ) from exc
                raise
            log.debug("Files report is: %s", files_report)
            for failed_file in files_report.failed:
                log.error("Failed to add file '%s'", failed_file)
            for warning in files_report.warnings:
                log.warning(warning)
            for removed_file in files_report.removed:
                log.info("Removed file '%s'", removed_file)
            for added_file_dir_ref in files_report.added:
                if added_file_dir_ref in packages:
                    pkg = packages[added_file_dir_ref][0]
                    table.append([pkg.name, pkg.version, '"' + pkg.key + '"'])
                    del packages[added_file_dir_ref]
                else:
                    log.error(
                        "Package %s added but won't displayed in output",
                        added_file_dir_ref,
                    )
            if packages:
                log.error(
                    "Could not match all added dir refs with uploaded packages for this packages: %s",
                    packages,
                )
            table.sort()
            print_table(
                table, ["package_name", "package_version", "package_key_quoted"]
            )
        finally:
            aptly.files_delete_dir(directory)

        if update_publishes:
            update_dependent_publishes(aptly, [repo], False)

    parser.set_defaults(func=action)


def repo_remove(parser: argparse.ArgumentParser) -> None:
    """configure 'repo remove' subcommand"""
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="just show packages to be removed",
    )
    parser.add_argument(
        "-U",
        "--update-publishes",
        action="store_true",
        help="update dependent publishes",
    )
    parser.add_argument(
        "repo_name", metavar="<repo_name>", help="local repository name"
    )
    parser.add_argument(
        "package_query", metavar="<package_query>", help="package query"
    )

    def action(
        *,
        aptly: Client,
        dry_run: bool,
        update_publishes: bool,
        repo_name: str,
        package_query: str,
        **_unused: Any,
    ) -> None:
        packages = aptly.repo_search(repo_name, package_query)
        if not packages:
            print("Nothing to remove")
            return
        packages.sort()
        if dry_run:
            print_table([[p.key] for p in packages], [f"Would delete from {repo_name}"])
        else:
            aptly.repo_delete_packages_by_key(repo_name, [p.key for p in packages])
            print_table([[p.key] for p in packages], [f"Deleted from {repo_name}"])

        if update_publishes:
            update_dependent_publishes(aptly, [repo_name], dry_run)

    parser.set_defaults(func=action)


def repo_copy_or_move(parser: argparse.ArgumentParser, move: bool) -> None:
    """configure 'repo copy' and 'repo move' subcommands"""
    parser.add_argument(
        "src_repo_name", metavar="<src_repo_name>", help="source local repo name"
    )
    parser.add_argument(
        "dst_repo_name", metavar="<dst_repo_name>", help="destination local repo name"
    )
    parser.add_argument(
        "queries",
        nargs="*",
        default=("",),
        metavar="<package_query>",
        help="package query",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="don't do anything, just show packages to be transfered",
    )
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="follow dependencies when processing package query",
    )
    parser.add_argument(
        "-U",
        "--update-publishes",
        action="store_true",
        help="update dependent publishes",
    )

    operation = "move" if move else "copy"

    def action(
        *,
        aptly: Client,
        src_repo_name: str,
        dst_repo_name: str,
        queries: List[str],
        dry_run: bool,
        with_deps: bool,
        update_publishes: bool,
        max_workers: int,
        **_unused: Any,
    ) -> None:
        try:
            aptly.repo_show(src_repo_name)
        except AptlyApiError as exc:
            if exc.status == 404:
                raise AptlyCtlError(f"{operation.capitalize()} failed") from exc
            raise

        result, errors = search(
            aptly,
            queries,
            with_deps=with_deps,
            max_workers=max_workers,
            store_filter=re.compile(f"^{src_repo_name}$"),
            search_snapshots=False,
        )

        for error in errors:
            log.error(error)
        if errors:
            raise AptlyCtlError(
                f"Package search in {src_repo_name} finished with errors"
            )
        if not result:
            raise AptlyCtlError(f"No packages found to {operation}")

        pkgs = set()
        for repo, packages in result:
            # seems no way we fail here, but just in case abort execution
            assert repo.name == src_repo_name
            pkgs.update(packages)

        table = [
            [
                src_repo_name,
                dst_repo_name,
                pkg.name,
                pkg.version,
                pkg.dir_ref,
                f'"{pkg.key}"',
            ]
            for pkg in pkgs
        ]
        table.sort()
        print_table(
            table, ["source", "destination", "name", "version", "dir_ref", "key"]
        )

        keys = [pkg.key for pkg in pkgs]
        try:
            log.info("Adding packages to '%s'", dst_repo_name)
            if not dry_run:
                aptly.repo_add_packages_by_key(dst_repo_name, keys)
        except AptlyApiError as exc:
            if exc.status in [400, 404]:
                raise AptlyCtlError(
                    "Failed to add packages to destination local repo"
                ) from exc
            raise

        pubs_to_update = [dst_repo_name]

        if move:
            log.info("Removing packages from source repo '%s'", src_repo_name)
            if not dry_run:
                aptly.repo_delete_packages_by_key(src_repo_name, keys)
            pubs_to_update.append(src_repo_name)

        if update_publishes:
            update_dependent_publishes(aptly, pubs_to_update, dry_run)

    parser.set_defaults(func=action)


def snapshot_create(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot create'"""
    parser.add_argument(
        "snapshot_name", metavar="<snapshot name>", help="snapshot name"
    )
    parser.add_argument(
        "-r",
        "--repo-name",
        help="""create from local repo.
        If absent, empty snapshot is created""",
    )
    parser.add_argument(
        "-d",
        "--description",
        dest="snapshot_desc",
        help="description string for a snapshot",
    )

    def action(
        *,
        aptly: Client,
        snapshot_name: str,
        repo_name: str,
        snapshot_desc: str,
        **_unused: Any,
    ) -> None:
        if repo_name:
            try:
                snapshot = aptly.snapshot_create_from_repo(
                    repo_name, snapshot_name, snapshot_desc
                )
            except AptlyApiError as exc:
                if exc.status in [400, 404]:
                    raise AptlyCtlError(
                        f"Failed to create snapshot '{snapshot_name}'"
                    ) from exc
                raise
        else:
            try:
                snapshot = aptly.snapshot_create_from_package_keys(
                    snapshot_name, keys=[], description=snapshot_desc
                )
            except AptlyApiError as exc:
                if exc.status == 400:
                    raise AptlyCtlError(
                        f"Failed to create snapshot '{snapshot_name}'"
                    ) from exc
                raise
        print_table([list(snapshot)], header=list(snapshot._fields))

    parser.set_defaults(func=action)


def snapshot_edit(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot edit'"""
    parser.add_argument(
        "snapshot_name", metavar="<snapshot name>", help="snapshot name"
    )
    parser.add_argument(
        "new_snapshot_name",
        nargs="?",
        default="",
        metavar="<new snapshot name>",
        help="snapshot name",
    )
    parser.add_argument(
        "-d",
        "--description",
        default="",
        dest="snapshot_desc",
        help="set new description string for a snapshot",
    )

    def action(
        *,
        aptly: Client,
        snapshot_name: str,
        new_snapshot_name: str,
        snapshot_desc: str,
        **_unused: Any,
    ) -> None:
        try:
            snapshot = aptly.snapshot_edit(
                snapshot_name, new_snapshot_name, snapshot_desc
            )
        except AptlyApiError as exc:
            if exc.status in [404, 409]:
                raise AptlyCtlError(
                    f"Failed to edit snapshot '{snapshot_name}'"
                ) from exc
            raise
        print_table([list(snapshot)], header=list(snapshot._fields))

    parser.set_defaults(func=action)


def snapshot_list(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot list' subcommand"""

    def action(
        *,
        aptly: Client,
        **_unused: Any,
    ) -> None:
        snapshots = aptly.snapshot_list()
        if not snapshots:
            print("No snapshots!")
            return
        header = list(snapshots[0]._fields)
        table = [list(snapshot) for snapshot in sorted(snapshots)]
        print_table(table, header=header)

    parser.set_defaults(func=action)


def snapshot_drop(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot drop' subcommand"""
    parser.add_argument(
        "snapshot_name", metavar="<snapshot name>", help="snapshot name"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="delete snapshot even if it's pointed by another snapshot",
    )

    def action(
        *, aptly: Client, snapshot_name: str, force: bool, **_unused: Any
    ) -> None:
        try:
            aptly.snapshot_delete(snapshot_name, force)
        except AptlyApiError as exc:
            if exc.status in [404, 409]:
                raise AptlyCtlError(
                    f"Failed to delete snapshot '{snapshot_name}'"
                ) from exc
            raise
        print(f"Deleted snapshot '{snapshot_name}'")

    parser.set_defaults(func=action)


def snapshot_filter(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot filter'"""
    parser.add_argument("source", metavar="<source>", help="source snapshot name")
    parser.add_argument(
        "destination", metavar="<destination>", help="destination snapshot name"
    )
    parser.add_argument(
        "queries", nargs="+", metavar="<package_query>", help="package query"
    )
    parser.add_argument(
        "--with-deps",
        action="store_true",
        help="include dependencies of matching packages",
    )

    def action(
        *,
        aptly: Client,
        source: str,
        destination: str,
        queries: List[str],
        with_deps: bool,
        max_workers: int,
        **_unused: Any,
    ) -> None:
        result, errors = search(
            aptly,
            queries,
            with_deps,
            max_workers=max_workers,
            store_filter=re.compile(f"^{source}$"),
            search_repos=False,
        )

        for error in errors:
            log.error(error)
        if errors:
            raise AptlyCtlError("Failed to filter packages")

        pkgs = set()
        for snap, packages in result:
            assert snap.name == source
            pkgs.update(packages)

        try:
            filtered_snap = aptly.snapshot_create_from_package_keys(
                destination,
                [pkg.key for pkg in pkgs],
                source_snapshots=[source],
                description=f"Filtered '{source}', queries were: {queries}",
            )
        except AptlyApiError as exc:
            if exc.status in [400, 404]:
                raise AptlyCtlError("Failed to create destination snapshot") from exc
            raise

        print_table(
            [
                [
                    filtered_snap.name,
                    filtered_snap.description,
                    filtered_snap.created_at,
                ]
            ],
            header=["name", "description", "created_at"],
        )

    parser.set_defaults(func=action)


def snapshot_merge(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot merge'"""
    # pylint: disable=too-many-statements

    parser.add_argument(
        "destination",
        metavar="<destination>",
        help="a snapshot name that will be created",
    )
    parser.add_argument(
        "sources",
        metavar="<source>",
        nargs="+",
        help=" snapshot name that will be merged",
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-l",
        "--latest",
        action="store_true",
        help="merge only the latest version of each package",
    )
    group.add_argument(
        "-k",
        "--keep",
        "--no-remove",
        dest="keep",
        action="store_true",
        help="preserve all versions of packages during merge",
    )

    class Mode(Enum):
        """
        latest_snap - from the packages with the same name and arch
        a package from the latest snapshot is picked.
        latest_ver - from the packages with the same name and arch
        a package with the latest version is picked.
        copy - merge all packages.
        """

        latest_snap = "latest snapshot"
        latest_ver = "latest version"
        copy = "copy"

    def merge_latest_snap(
        search_result: List[Tuple[Union[Repo, Snapshot], List[Package]]],
        sources: List[str],
    ) -> Generator[Package, None, None]:
        pkgs: Dict[str, Tuple[Package, datetime]]
        for snap, packages in search_result:
            snap = cast(Snapshot, snap)
            assert snap.name in sources
            for pkg in packages:
                key = pkg.name + pkg.arch
                if key in pkgs:
                    if snap.created_at > pkgs[key][1]:
                        pkgs[key] = (pkg, snap.created_at)
                    elif (
                        snap.created_at == pkgs[key][1]
                        and pkg.version > pkgs[key][0].version
                    ):
                        pkgs[key] = (pkg, snap.created_at)
                else:
                    pkgs[key] = (pkg, snap.created_at)
        return (pkg for pkg, _ in pkgs.values())

    def merge_latest_ver(
        search_result: List[Tuple[Union[Repo, Snapshot], List[Package]]],
        sources: List[str],
    ) -> Generator[Package, None, None]:
        pkgs: Dict[str, Package]
        for snap, packages in search_result:
            snap = cast(Snapshot, snap)
            assert snap.name in sources
            for pkg in packages:
                key = pkg.name + pkg.arch
                if key in pkgs:
                    if pkg.version > pkgs[key].version:
                        pkgs[key] = pkg
                else:
                    pkgs[key] = pkg
        return (pkg for pkg in pkgs.values())

    def action(
        *,
        aptly: Client,
        destination: str,
        sources: List[str],
        latest: bool,
        keep: bool,
        max_workers: int,
        **_unused: Any,
    ) -> None:
        if keep or len(sources) == 1:
            mode = Mode.copy
            if latest:
                log.warning(
                    "--latest flag is ignored since there is only one source snapshot"
                )
        elif latest:
            mode = Mode.latest_ver
        else:
            mode = Mode.latest_snap

        result, errors = search(
            aptly,
            max_workers=max_workers,
            store_filter=re.compile(f"^({'|'.join(sources)})$"),
            search_repos=False,
        )

        for error in errors:
            log.error(error)
        if errors:
            raise AptlyCtlError("Failed to merge packages")

        pkgs = set()

        if mode is Mode.copy:
            for snap, packages in result:
                assert snap.name in sources
                pkgs.update(packages)
        elif mode is Mode.latest_snap:
            pkgs.update(merge_latest_snap(result, sources))
        elif mode is Mode.latest_ver:
            pkgs.update(merge_latest_ver(result, sources))

        try:
            merged_snap = aptly.snapshot_create_from_package_keys(
                destination,
                [pkg.key for pkg in pkgs],
                source_snapshots=sources,
                description=f"""Merged ({mode.value}) from sources: '{"', '".join(sources)}'""",
            )
        except AptlyApiError as exc:
            if exc.status in [400, 404]:
                raise AptlyCtlError("Failed to create destination snapshot") from exc
            raise

        print_table(
            [[merged_snap.name, merged_snap.description, merged_snap.created_at]],
            header=["name", "description", "created_at"],
        )

    parser.set_defaults(func=action)


def snapshot_diff(parser: argparse.ArgumentParser) -> None:
    """configure 'snapshot diff'"""
    parser.add_argument("snap_left", help="snapshot name")
    parser.add_argument("snap_right", help="snapshot name")

    def action(
        *,
        aptly: Client,
        snap_left: str,
        snap_right: str,
        **_unused: Any,
    ) -> None:
        table = []
        for left, right in aptly.snapshot_diff(snap_left, snap_right):
            left_str = "" if left is None else left.key
            right_str = "" if right is None else right.key
            table.append([left_str, right_str])
        print_table(table, [snap_left, snap_right])

    parser.set_defaults(func=action)


def print_publishes(pubs: Iterable[Publish]) -> None:
    """print a list of Publish instances to stdout"""
    leading_fields = ["source_kind", "distribution", "prefix", "storage"]
    header = list(Publish._fields)
    for field in leading_fields:
        header.remove(field)
        header.insert(0, field)
    table = [[getattr(pub, attr) for attr in header] for pub in pubs]
    for index in range(len(leading_fields) - 1, -1, -1):
        # pylint: disable=cell-var-from-loop
        table.sort(key=lambda row: row[index])
    print_table(table, header=header)


def publish_list(parser: argparse.ArgumentParser) -> None:
    """configure 'publish list' subcommand"""

    def action(
        *,
        aptly: Client,
        **_unused: Any,
    ) -> None:
        pubs = aptly.publish_list()
        if not pubs:
            print("There are no publishes!")
            return
        print_publishes(pubs)

    parser.set_defaults(func=action)


def publish_create(
    parser: argparse.ArgumentParser, snapshot_action: bool = True
) -> None:
    """configure 'publish repo' and 'publish snapshot' subcommands"""

    if snapshot_action:
        parser.add_argument(
            "source_names",
            metavar="<snapshot_name>",
            nargs="+",
            help="snapshot name to publish",
        )
    else:
        parser.add_argument(
            "source_names",
            metavar="<repo_name>",
            nargs="+",
            help="repo name to publish",
        )

    parser.add_argument(
        "-s",
        "--storage",
        metavar="<storage>",
        default="",
        help="Storage type to publish to. If absent, aptly server local filesystem is assumed",
    )

    parser.add_argument(
        "-p",
        "--prefix",
        metavar="<prefix>",
        default="",
        help="prefix for publishing. If not specified, sources would be published"
        " to the root of the public directory",
    )

    parser.add_argument(
        "-d",
        "--distribution",
        metavar="<distribution>",
        default="",
        help="distribution name to publish. If absent, guessed from original repository distribution",
    )

    parser.add_argument(
        "-c",
        "--components",
        type=str_list,
        default="",
        metavar="<component>[,<component>,...]",
        help="component name to publish. Guessed from original repository (if any), or defaults to main."
        " For multi-component publishing, separate components with commas",
    )

    parser.add_argument(
        "-a",
        "--architectures",
        type=str_list,
        default="",
        metavar="<architecture>[,<architecture>,...]",
        help="override default list of architectures to be published",
    )

    parser.add_argument(
        "--label",
        metavar="<label>",
        default="",
        help="value for Label: field",
    )

    parser.add_argument(
        "--origin",
        metavar="<origin>",
        default="",
        help="value for Origin: field",
    )

    parser.add_argument(
        "--acquire-by-hash",
        action="store_true",
        help="provide index files by hash if unique",
    )

    parser.add_argument(
        "--not-automatic",
        action="store_true",
        help="Set NotAutomatic: field to 'yes'",
    )

    parser.add_argument(
        "--but-automatic-upgrades",
        action="store_true",
        help="set ButAutomaticUpgrades: field to 'yes'. Can't be set without --not-automatic",
    )

    parser.add_argument(
        "--force-overwrite",
        action="store_true",
        help="overwrite files in pool/ directory without notice",
    )

    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="don’t remove unreferenced files in prefix/component",
    )

    def action(
        *,
        aptly: Client,
        source_names: List[str],
        storage: str,
        prefix: str,
        distribution: str,
        components: List[str],
        architectures: List[str],
        label: str,
        origin: str,
        acquire_by_hash: bool,
        not_automatic: bool,
        but_automatic_upgrades: bool,
        force_overwrite: bool,
        skip_cleanup: bool,
        **_unused: Any,
    ) -> None:
        if but_automatic_upgrades and not not_automatic:
            raise AptlyCtlError(
                "Can't set --but-automatic-upgrades without setting --not-automatic. "
                "It is against Debian policy: "
                + DEBIAN_POLICY_BUT_AUTOMATIC_UPGRADES_LINK
            )

        source_kind = "snapshot" if snapshot_action else "local"

        if components and len(components) != len(source_names):
            raise AptlyCtlError(
                "If you provide components, provide them for every source"
            )

        if components:
            sources = [
                Source(name, comp) for name, comp in zip(source_names, components)
            ]
        else:
            sources = [Source(name) for name in source_names]

        pub = aptly.publish_create(
            source_kind=source_kind,
            sources=sources,
            storage=storage,
            prefix=prefix,
            distribution=distribution,
            architectures=architectures,
            label=label,
            origin=origin,
            not_automatic=not_automatic,
            but_automatic_upgrades=but_automatic_upgrades,
            acquire_by_hash=acquire_by_hash,
            force_overwrite=force_overwrite,
            skip_cleanup=skip_cleanup,
        )

        print_publishes([pub])

    parser.set_defaults(func=action)


def publish_update(parser: argparse.ArgumentParser) -> None:
    """configure 'publish update' subcommand"""

    parser.add_argument(
        "distribution",
        metavar="<distribution>",
        help="distribution of a publish to drop",
    )

    parser.add_argument(
        "endpoint_and_prefix",
        metavar="[<endpoint>:]<prefix>",
        nargs="?",
        default="",
        help="""
        <endpoint> - publishing endpoint, if not specified, it would default to empty endpoint (local file system).
        <prefix> - publishing prefix, if not specified, it would default to empty prefix (.)
        """,
    )

    parser.add_argument(
        "-f",
        "--force-overwrite",
        action="store_true",
        help="overwrite packages files in the pool even if content is different",
    )

    def action(
        *,
        aptly: Client,
        distribution: str,
        endpoint_and_prefix: str,
        force_overwrite: bool,
        **_unused: Any,
    ) -> None:
        storage, _, prefix = endpoint_and_prefix.rpartition(":")
        publish = aptly.publish_update(
            force_overwrite=force_overwrite,
            distribution=distribution,
            storage=storage,
            prefix=prefix,
        )
        print_publishes([publish])

    parser.set_defaults(func=action)


def publish_switch(parser: argparse.ArgumentParser) -> None:
    """configure 'publish switch' subcommand"""

    parser.add_argument(
        "distribution",
        metavar="<distribution>",
        help="distribution of a publish to drop",
    )

    parser.add_argument(
        "endpoint_and_prefix",
        metavar="[<endpoint>:]<prefix>",
        nargs="?",
        default="",
        help="""
       <endpoint> - publishing endpoint, if not specified, it would default to empty endpoint (local file system).
       <prefix> - publishing prefix, if not specified, it would default to empty prefix (.)
       """,
    )

    parser.add_argument(
        "new_snapshot_names",
        metavar="<new snapshot name>",
        nargs="+",
        help="snapshot name that snould be re-published",
    )

    parser.add_argument(
        "-c",
        "--components",
        type=str_list,
        default="main",
        metavar="<component>[,<component>,...]",
        help="""when switching published snapshots for multiple component repositories
        any subset of snapshots could be updated,
        they should be listed in this argument, separated by comas. For single component repo
        you can skip this argument
        """,
    )

    parser.add_argument(
        "-f",
        "--force-overwrite",
        action="store_true",
        help="overwrite packages files in the pool even if content is different",
    )

    def action(
        *,
        aptly: Client,
        distribution: str,
        endpoint_and_prefix: str,
        new_snapshot_names: List[str],
        components: List[str],
        force_overwrite: bool,
        **_unused: Any,
    ) -> None:
        storage, _, prefix = endpoint_and_prefix.rpartition(":")

        if len(components) != len(new_snapshot_names):
            raise AptlyCtlError(
                "For multiple component publishes specify component for each updated snapshot"
            )

        sources = [
            Source(name, comp) for name, comp in zip(new_snapshot_names, components)
        ]

        publish = aptly.publish_update(
            force_overwrite=force_overwrite,
            distribution=distribution,
            storage=storage,
            prefix=prefix,
            snapshots=sources,
        )

        print_publishes([publish])

    parser.set_defaults(func=action)


def publish_drop(parser: argparse.ArgumentParser) -> None:
    """configure 'publish drop' subcommand"""

    parser.add_argument(
        "distribution",
        metavar="<distribution>",
        help="distribution of a publish to drop",
    )

    parser.add_argument(
        "endpoint_and_prefix",
        metavar="[<endpoint>:]<prefix>",
        nargs="?",
        default="",
        help="""
        <endpoint> - publishing endpoint, if not specified, it would default to empty endpoint (local file system).
        <prefix> - publishing prefix, if not specified, it would default to empty prefix (.)
        """,
    )

    parser.add_argument(
        "-f",
        "--force-drop",
        action="store_true",
        help="force published repository removal even if component cleanup fails",
    )

    def action(
        *,
        aptly: Client,
        distribution: str,
        endpoint_and_prefix: str,
        force_drop: bool,
        **_unused: Any,
    ) -> None:
        storage, _, prefix = endpoint_and_prefix.rpartition(":")
        aptly.publish_drop(
            distribution=distribution, storage=storage, prefix=prefix, force=force_drop
        )

    parser.set_defaults(func=action)


def parse_args() -> argparse.Namespace:
    """parse command line arguments"""
    parser = argparse.ArgumentParser(prog="aptly-ctl")

    parser.add_argument("--version", action="version", version="%(prog)s " + VERSION)

    log_level_parser = parser.add_mutually_exclusive_group()
    log_level_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="be more verbose",
    )

    log_level_parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug messages",
    )

    parser.add_argument("-c", "--config", help="path to config file")

    parser.add_argument(
        "-S",
        "--section",
        default="",
        help="section from config file. By default first one is used",
    )

    parser.add_argument(
        "-C",
        "--config-key",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        dest="config_keys",
        help="""
        provide value for configuration KEY.
        Takes precedence over config file.
        Use dots to set nested fields e.g. signing.gpgkey=somekey
        """,
    )

    parser.add_argument(
        "--max-workers",
        type=int,
        default=5,
        help="number of worker threads for concurrent requests",
    )

    subcommands = parser.add_subparsers(
        dest="subcommand", metavar="<subcommand>", required=True
    )

    # version subcommand
    version(
        subcommands.add_parser(
            "version",
            aliases=["ver"],
            description="show aptly server version",
            help="show aptly server version",
        )
    )

    # package subcommand
    package_subcommand = subcommands.add_parser(
        "package", aliases=["pkg"], help="search packages and show info about them"
    )

    package_actions = package_subcommand.add_subparsers(
        dest="action", metavar="<action>", required=True
    )

    package_show(package_actions.add_parser("show", help="show package info"))

    package_search(
        package_actions.add_parser(
            "search", description="search packages", help="search packages"
        )
    )

    package_remove(
        package_actions.add_parser(
            "remove",
            description="remove packages from all local repos",
            help="remove packages from all local repos",
        )
    )

    # repo subcommand
    repo_subcommand = subcommands.add_parser(
        "repo", help="manage local repos and add packages to them"
    )

    repo_actions = repo_subcommand.add_subparsers(
        dest="action", metavar="<action>", required=True
    )

    repo_create_or_edit(
        repo_actions.add_parser(
            "create",
            description="create local package repository",
            help="create local package repository",
        ),
        False,
    )

    repo_create_or_edit(
        repo_actions.add_parser(
            "edit",
            description="edit local package repository",
            help="edit local package repository",
        ),
        True,
    )

    repo_add(
        repo_actions.add_parser(
            "add",
            description="add packages to local repository from .deb (binary packages)",
            help="add packages to local repository from .deb (binary packages)",
        )
    )

    repo_list(
        repo_actions.add_parser(
            "list", description="list local repos", help="list local repos"
        )
    )

    repo_drop(
        repo_actions.add_parser(
            "drop",
            aliases=["delete"],
            description="delete local repos",
            help="delete local repos",
        )
    )

    repo_remove(
        repo_actions.add_parser(
            "remove",
            description="remove packages from local repo",
            help="remove packages from local repo",
        )
    )

    repo_copy_or_move(
        repo_actions.add_parser(
            "copy",
            description="copy packages between local repos",
            help="copy packages between local repos",
        ),
        False,
    )

    repo_copy_or_move(
        repo_actions.add_parser(
            "move",
            description="move packages between local repos",
            help="move packages between local repos",
        ),
        True,
    )

    # snapshot subcommand
    snapshot_subcommand = subcommands.add_parser(
        "snapshot", aliases=["snap"], help="manage snapshots"
    )

    snapshot_actions = snapshot_subcommand.add_subparsers(
        dest="action", metavar="<action>", required=True
    )

    snapshot_create(
        snapshot_actions.add_parser(
            "create",
            description="create snapshots from local repos",
            help="create snapshots from local repos",
        )
    )

    snapshot_edit(
        snapshot_actions.add_parser(
            "edit",
            aliases=["rename"],
            description="Change snapshot's description or name",
            help="Change snapshot's description or name",
        )
    )

    snapshot_list(
        snapshot_actions.add_parser(
            "list", description="list snapshots", help="list snapshots"
        )
    )

    snapshot_drop(
        snapshot_actions.add_parser(
            "drop",
            aliases=["delete"],
            description="delete snapshots",
            help="delete snapshots",
        )
    )

    snapshot_filter(
        snapshot_actions.add_parser(
            "filter",
            description="appplies filter to contents of one snapshot producing another snapshot",
            help="appplies filter to contents of one snapshot producing another snapshot",
        )
    )

    snapshot_merge(
        snapshot_actions.add_parser(
            "merge",
            help="merges several source snapshots into new destination snapshot",
            description="""Merges several source snapshots into new destination snapshot.
            By default, packages with the same name-architecture pair
            are replaced during merge (package from latest snapshot on the list wins).
            With --latest flag, package with latest version wins.
            With --no-remove flag, all versions of packages are preserved during merge.
            If only one snapshot is specified, merge copies source into destination.
            """,
        )
    )

    snapshot_diff(
        snapshot_actions.add_parser(
            "diff",
            description="displays difference in packages between two snapshots",
            help="displays difference in packages between two snapshots",
        )
    )

    # publish subcommand
    publish_subcommand = subcommands.add_parser(
        "publish",
        aliases=["pub"],
        help="create publishes from local repos or snapshots and manage them",
    )

    publish_actions = publish_subcommand.add_subparsers(
        dest="action", metavar="<action>", required=True
    )

    publish_list(
        publish_actions.add_parser(
            "list", description="list publishes", help="list publishes"
        )
    )

    publish_create(
        publish_actions.add_parser(
            "snapshot",
            description="publishes snapshot as repository to be consumed by apt",
            help="publishes snapshot as repository to be consumed by apt",
        ),
        True,
    )

    publish_create(
        publish_actions.add_parser(
            "repo",
            description="publish local repository directly, bypassing snapshot creation step",
            help="publish local repository directly, bypassing snapshot creation step",
        ),
        False,
    )

    publish_update(
        publish_actions.add_parser(
            "update",
            description="re-publish (update) published local repository",
            help="re-publish (update) published local repository",
        )
    )

    publish_switch(
        publish_actions.add_parser(
            "switch",
            description="switch in-place published repository with new snapshot contents",
            help="switch in-place published repository with new snapshot contents",
        )
    )

    publish_drop(
        publish_actions.add_parser(
            "drop", description="drop publishes", help="drop publishes"
        )
    )

    return parser.parse_args()


def main() -> None:
    """entrypoint for command line"""
    args = parse_args()

    log_level = logging.WARN
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    log_format = "%(levelname)s "
    if hasattr(args, "action"):
        log_format += args.subcommand + "->" + args.action + "(%(process)d) "
    else:
        log_format += args.subcommand + "(%(process)d) "
    if log_level <= logging.DEBUG:
        log_format += "[%(name)s:%(funcName)s()] "
    log_format += "%(message)s"

    app_logger = logging.getLogger(__package__)
    app_logger.setLevel(log_level)
    app_log_formatter = logging.Formatter(fmt=log_format)
    app_log_handler = logging.StreamHandler()
    app_log_handler.setFormatter(app_log_formatter)
    app_logger.addHandler(app_log_handler)
    if log_level <= logging.DEBUG:
        urllib3_logger = logging.getLogger("urllib3")
        urllib3_logger.setLevel(log_level)
        urllib3_logger.addHandler(app_log_handler)

    override = parse_override_dict(args.config_keys)
    config = Config(path=args.config, section=args.section, override=override)
    aptly = Client(
        url=config.url,
        default_signing_config=config.default_signing_config,
        signing_config_map=config.signing_config_map,
        timeout=Timeout(connect=config.connect_timeout, read=config.read_timeout),
    )

    try:
        args.func(aptly=aptly, **vars(args))
    except urllib3.exceptions.HTTPError as exc:
        log.error("Failed to communicate with aptly API: %s", exc)
        log.debug("Printing traceback for error above", exc_info=True)
        sys.exit(1)
    except AptlyCtlError as exc:
        error_msg = str(exc)
        if exc.__cause__ is not None:
            error_msg += f": {exc.__cause__}"
        elif exc.__context__:
            error_msg += f": {exc.__context__}"
        log.error(error_msg)
        log.debug("Printing traceback for error above", exc_info=True)
        sys.exit(2)
