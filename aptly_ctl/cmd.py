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
    NamedTuple,
    Tuple,
    Dict,
    Pattern,
    Container,
)
import json
import sys
import os
from datetime import datetime
import string
import urllib3.exceptions
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


class PipeMessage(NamedTuple):
    """Message that is passsed in pipe between aptly-ctl instances"""

    message: List[Tuple[Union[Repo, Snapshot], List[Package]]]

    def to_json(self) -> str:
        """Serialize to json"""
        msg = []
        for store, packages in self.message:
            if isinstance(store, Snapshot):
                store_raw: Dict[str, Union[str, List[str]]] = {
                    "type": "Snapshot",
                    "name": store.name,
                    "description": store.description,
                    "created_at": store.created_at.isoformat()
                    if store.created_at
                    else "",
                }
            elif isinstance(store, Repo):
                store_raw = {
                    "type": "Repo",
                    "name": store.name,
                    "comment": store.comment,
                    "default_distribution": store.default_distribution,
                    "default_component": store.default_component,
                }
            else:
                raise TypeError("Invalid store type: " + str(type(store)))
            store_raw["packages"] = [package.key for package in packages]
            msg.append(store_raw)
        return json.dumps(msg)

    @classmethod
    def from_json(cls, msg: str) -> "PipeMessage":
        """Build PipeMessage from json"""
        message = []
        stores_raw = json.loads(msg)
        for store_raw in stores_raw:
            if store_raw["type"] == "Snapshot":
                store: Union[Repo, Snapshot] = Snapshot(
                    name=store_raw["name"],
                    description=store_raw["description"],
                    created_at=datetime.fromisoformat(store_raw["created_at"])
                    if store_raw["created_at"]
                    else None,
                )
            elif store_raw["type"] == "Repo":
                store = Repo(
                    name=store_raw["name"],
                    comment=store_raw["comment"],
                    default_distribution=store_raw["default_distribution"],
                    default_component=store_raw["default_component"],
                )
            else:
                raise ValueError(
                    "store "
                    + store_raw["name"]
                    + " has invalid type "
                    + store_raw["type"]
                )
            packages = [Package.from_key(key) for key in store_raw["packages"]]
            message.append((store, packages))
        return cls(message)


class SetOrReadPipeMessage(argparse.Action):  # pylint: disable=too-few-public-methods
    """argparse action which sets argument value as usual if it is present
    or tries to read it from a PipeMessage supplied from the stdin if is is not a tty"""

    def __call__(self, parser, namespace, values, option_string=None):  # type: ignore
        if values:
            setattr(namespace, self.dest, values)
            return
        if not sys.stdin.isatty():
            try:
                msg = PipeMessage.from_json(sys.stdin.read())
            except json.JSONDecodeError as exc:
                raise argparse.ArgumentError(
                    self, "failed to decode pipe message from stdin: " + str(exc)
                )
            setattr(namespace, self.dest, msg)
            return
        raise argparse.ArgumentError(
            self,
            "arguments were not supplied neither from the command line nor from the stdin!",
        )


def update_dependent_publishes(
    aptly: Client,
    repo_names: Container[str],
    dry_run: bool,
) -> None:
    """Find and update publishes, that were created from local repos, listed in repo_names argument"""
    publishes = []
    for publish in aptly.publish_list():
        if publish.source_kind != "local":
            continue
        for source in publish.sources:
            if source.name in repo_names:
                publishes.append(publish)

    if not publishes:
        return
    print()

    if dry_run:
        print_table([[p] for p in publishes], ["Publishes to update"])
        return

    updated_publishes = []
    failed_to_updated_publishes = []
    for publish in publishes:
        try:
            updated_publishes.append(aptly.publish_update(publish))
        except AptlyApiError as exc:
            failed_to_updated_publishes.append([publish, int(exc.status), exc])

    print_table([[p] for p in updated_publishes], ["Updated publishes"])

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
        "keys",
        metavar="<key>",
        action=SetOrReadPipeMessage,
        nargs="*",
        help="package key",
    )

    first_fileds = ["Package", "Version", "Architecture"]
    last_fields = ["Description"]
    skip_fields = set(first_fileds) | set(last_fields) | {"Key", "ShortKey"}

    def action(
        *, aptly: Client, keys: Union[Iterable[str], PipeMessage], **_unused: Any
    ) -> None:
        missing_pkgs = False
        if isinstance(keys, PipeMessage):
            msg = keys
            keys = {package.key for _, packages in msg.message for package in packages}
        for key in keys:
            try:
                package = aptly.package_show(key)
            except AptlyApiError as exc:
                if exc.status == 404:
                    log.error("Package with key '%s' wasn't found", key)
                    log.debug("Printing traceback for error above", exc_info=True)
                    missing_pkgs = True
                    continue
                raise
            if not package.fields:
                raise RuntimeError(
                    "'fileds' attribute of Package object was not present"
                )
            print('"', package.key, '"', sep="")
            for field in first_fileds:
                print("   ", field, ":", package.fields[field])
            for field in sorted(package.fields.keys()):
                if field in skip_fields:
                    continue
                print("   ", field, ":", package.fields[field])
            for field in last_fields:
                print("   ", field, ":", package.fields[field])
        if missing_pkgs:
            raise AptlyCtlError("Some packages were not found")

    parser.set_defaults(func=action)


def package_search(parser: argparse.ArgumentParser) -> None:
    """configure 'package search' subcommand"""

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
        dest="base_out_columns_str",
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
        dest="extra_out_columns_str",
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
                row.append(size_pretty(int(package.fields[col]) * 1024))
            elif col == "Size":
                row.append(size_pretty(int(package.fields[col])))
            elif col[0] in string.ascii_uppercase:
                try:
                    row.append(package.fields[col])
                except KeyError:
                    raise AptlyCtlError("Unknown output column name: " + col)
            else:
                raise AptlyCtlError("Unknown output column name: " + col)
        return row

    def action(
        *,
        aptly: Client,
        queries: Iterable[str],
        with_deps: bool,
        base_out_columns_str: str,
        extra_out_columns_str: str,
        max_workers: int,
        store_filter: Optional[Pattern],
        sort_reverse: bool,
        assume_tty: bool,
        no_header: bool,
        **_unused: Any,
    ) -> None:
        base_out_columns = list(filter(None, base_out_columns_str.split(",")))
        extra_out_columns = list(filter(None, extra_out_columns_str.split(",")))
        out_columns = base_out_columns + extra_out_columns
        details = any(filter(lambda col: col[0] in string.ascii_uppercase, out_columns))

        result, errors = search(
            aptly,
            queries,
            with_deps,
            details,
            max_workers=max_workers,
            store_filter=store_filter,
        )
        if not sys.stdout.isatty() and not assume_tty:
            print(PipeMessage(result).to_json())
            return
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
        # TODO add ability to delete multiple repos
        # TODO read repos to delete from pipe message
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
        # TODO add ability to delete multiple snapshots
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
        "--component",
        metavar="<component>[,<component>,...]",
        help="component name to publish. Guessed from original repository (if any), or defaults to main."
        " For multi-component publishing, separate components with commas",
    )

    parser.add_argument(
        "-a",
        "--architectures",
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
        component: Optional[str],
        architectures: Optional[str],
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
        arch = architectures.split(",") if architectures else []
        comps = component.split(",") if component else []

        if comps and len(comps) != len(source_names):
            raise AptlyCtlError(
                "If you provide components, provide them for every source"
            )

        if comps:
            sources = [Source(name, comp) for name, comp in zip(source_names, comps)]
        else:
            sources = [Source(name) for name in source_names]

        pub = aptly.publish_create(
            source_kind=source_kind,
            sources=sources,
            storage=storage,
            prefix=prefix,
            distribution=distribution,
            architectures=arch,
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
        "--component",
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
        component: str,
        force_overwrite: bool,
        **_unused: Any,
    ) -> None:
        storage, _, prefix = endpoint_and_prefix.rpartition(":")
        comps = component.split(",") if component else ["main"]

        if len(comps) != len(new_snapshot_names):
            raise AptlyCtlError(
                "For multiple component publishes specify component for each updated snapshot"
            )

        sources = [Source(name, comp) for name, comp in zip(new_snapshot_names, comps)]

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

    parser.add_argument(
        "-a",
        "--assume-tty",
        action="store_true",
        help="assume stdout is always a tty. "
        "This disables json output when redirecting to a pipe/file",
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
