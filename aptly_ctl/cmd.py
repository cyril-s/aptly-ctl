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
    ClassVar,
    Set,
)
import json
import sys
from datetime import datetime
from aptly_ctl import VERSION
from aptly_ctl.aptly import Client, Repo, Snapshot, Package, search
from aptly_ctl.config import Config, parse_override_dict

# from aptly_ctl.exceptions import AptlyApiError

log = logging.getLogger(__name__)

PACKAGE_QUERY_DOC_URL = "https://www.aptly.info/doc/feature/query/"


def print_table(
    orig_table: List[List[Any]],
    header: List[str] = None,
    sep: str = " ",
    header_sep: str = "-",
    header_intersect_sep: str = " ",
) -> None:
    """Prints matrix orig_table converting every element to string as table"""
    if not orig_table:
        return
    table = [list(map(str, row)) for row in orig_table]
    if header:
        table.insert(0, header)
    col_sizes = [0 for _ in range(len(table[0]))]
    for row in table:
        for index, elem in enumerate(row):
            if len(elem) >= col_sizes[index]:
                col_sizes[index] = len(elem)
    if header:
        table.insert(1, [])
        for size in col_sizes:
            table[1].append(header_sep * size)
    for row_num, row in enumerate(table):
        for index, elem in enumerate(row):
            print(elem + " " * (col_sizes[index] - len(elem)), end="")
            if index < len(row) - 1:
                if header and row_num == 1:
                    print(header_intersect_sep, end="")
                else:
                    print(sep, end="")
        print()


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
                store_raw = {
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
        msg = json.loads(msg)
        for store_raw in msg:
            if store_raw["type"] == "Snapshot":
                store = Snapshot(
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


class SetOrReadPipeMessage(argparse.Action):
    """argparse action which sets argument value as usual if it is present
    or tries to read it from a PipeMessage supplied from the stdin if is is not a tty"""

    def __call__(self, parser, namespace, values, option_string=None):
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


class VersionCmd:
    """subcommand to get aptly server version"""

    @staticmethod
    def config(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(func=VersionCmd.action)

    @staticmethod
    def action(*, aptly: Client, **_unused: Any) -> None:
        print(aptly.version())


class PackageShowCmd:
    """subcommand to show aptly package info"""

    first_fileds: ClassVar[List[str]] = ["Package", "Version", "Architecture"]
    last_fields: ClassVar[List[str]] = ["Description"]
    skip_fields: ClassVar[Set[str]] = {
        "Package",
        "Version",
        "Architecture",
        "Description",
        "Key",
        "ShortKey",
    }

    @staticmethod
    def config(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(func=PackageShowCmd.action)
        parser.add_argument(
            "keys",
            metavar="<key>",
            action=SetOrReadPipeMessage,
            nargs="*",
            help="package key",
        )

    @staticmethod
    def action(
        *, aptly: Client, keys: Union[Iterable[str], PipeMessage], **_unused: Any
    ) -> None:
        if isinstance(keys, PipeMessage):
            msg = keys
            keys = {package.key for _, packages in msg.message for package in packages}
        for key in keys:
            package = aptly.package_show(key)
            print('"', package.key, '"', sep="")
            for field in PackageShowCmd.first_fileds:
                print("   ", field, ":", package.fields[field])
            for field in sorted(package.fields):
                if field in PackageShowCmd.skip_fields:
                    continue
                print("   ", field, ":", package.fields[field])
            for field in PackageShowCmd.last_fields:
                print("   ", field, ":", package.fields[field])


class PackageSearchCmd:
    """subcommand to search for aptly packages"""

    @staticmethod
    def config(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(func=PackageSearchCmd.action)
        parser.add_argument(
            "queries",
            metavar="[ query ... ]",
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
            dest="out_columns_str",
            metavar="OUT_COLUMNS",
            default="store_type,store_name,package_name,package_version,package_key_quoted",
            help="output columns",
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

    @staticmethod
    def action(
        *,
        aptly: Client,
        queries: Iterable[str],
        with_deps: bool,
        out_columns_str: str,
        max_workers: int,
        store_filter: Optional[re.Pattern],
        sort_reverse: bool,
        assume_tty: bool,
        **_unused: Any
    ) -> None:
        result, errors = search(
            aptly,
            queries,
            with_deps,
            max_workers=max_workers,
            store_filter=store_filter,
        )
        if not sys.stdout.isatty() and not assume_tty:
            print(PipeMessage(result).to_json())
            return
        out_columns = out_columns_str.split(",")
        table = [
            PackageSearchCmd.build_out_row(out_columns, store, package)
            for store, packages in result
            for package in packages
        ]
        for index in range(len(out_columns) - 1, -1, -1):
            table.sort(key=lambda row: row[index], reverse=sort_reverse)
        print_table(table, out_columns)
        for error in errors:
            log.error(error)

    @staticmethod
    def build_out_row(
        cols: Iterable[str], store: Union[Snapshot, Repo], package: Package
    ) -> List[Any]:
        """build a row in a table to be printed"""
        row = []
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
            else:
                raise ValueError("Unknown output column name: " + col)
        return row


def main() -> None:
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

    VersionCmd.config(
        subcommands.add_parser(
            "version",
            description="show aptly server version",
            help="show aptly server version",
        )
    )

    package_subcommand = subcommands.add_parser(
        "package", help="search packages and show info about them"
    )
    package_actions = package_subcommand.add_subparsers(
        dest="action", metavar="<action>", required=True
    )

    PackageShowCmd.config(package_actions.add_parser("show", help="show package info"))
    PackageSearchCmd.config(
        package_actions.add_parser("search", help="search packages")
    )

    args = parser.parse_args()

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

    args.func(aptly=aptly, **vars(args))
