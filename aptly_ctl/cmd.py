import argparse
import logging
import re
from typing import Iterable, Any, List, Union, Optional
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
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise argparse.ArgumentError(exc)


class VersionCmd:
    @staticmethod
    def config(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(func=VersionCmd.action)

    @staticmethod
    def action(*, aptly: Client, **_unused: Any) -> None:
        print(aptly.version())


class PackageShowCmd:
    @staticmethod
    def config(parser: argparse.ArgumentParser) -> None:
        parser.set_defaults(func=PackageShowCmd.action)
        parser.add_argument(
            "keys",
            metavar="key [ key ... ]",
            nargs="+",
            help="package key",
        )

    @staticmethod
    def action(*, aptly: Client, keys: Iterable[str], **_unused: Any) -> None:
        first_fileds = ["Package", "Version", "Architecture"]
        last_fields = ["Description"]
        skip_fields = set(first_fileds + last_fields + ["Key", "ShortKey"])
        for key in keys:
            package = aptly.package_show(key)
            print('"', package.key, '"', sep="")
            for field in first_fileds:
                print("   ", field, ":", package.fields[field])
            for field in sorted(package.fields):
                if field in skip_fields:
                    continue
                print("   ", field, ":", package.fields[field])
            for field in last_fields:
                print("   ", field, ":", package.fields[field])


class PackageSearchCmd:
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
        **_unused: Any
    ) -> None:
        result, errors = search(
            aptly,
            queries,
            with_deps,
            max_workers=max_workers,
            store_filter=store_filter,
        )
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

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase verbosity. Can be set mutiple times to increase verbosity even more",
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

    subcommands = parser.add_subparsers(dest="subcommand")

    VersionCmd.config(
        subcommands.add_parser("version", help="show aptly server version")
    )

    package_subcommand = subcommands.add_parser(
        "package", help="search packages and show info about them"
    )
    package_actions = package_subcommand.add_subparsers(dest="action")

    PackageShowCmd.config(package_actions.add_parser("show", help="show package info"))
    PackageSearchCmd.config(
        package_actions.add_parser("search", help="search packages")
    )

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        parser.exit(2)
    elif not args.action:
        # TODO show action help
        parser.print_help()
        parser.exit(2)

    verbosities = (logging.WARN, logging.INFO, logging.DEBUG)
    log_level = verbosities[min(args.verbose, len(verbosities) - 1)]
    log_format = "%(levelname)s " + args.subcommand + "(%(process)d)"
    if log_level >= logging.DEBUG:
        log_format += " [%(name)s:%(funcName)s()] %(message)s"
    else:
        log_format += " %(message)s"
    app_logger = logging.getLogger(__package__)
    app_logger.setLevel(log_level)
    app_log_formatter = logging.Formatter(fmt=log_format)
    app_log_handler = logging.StreamHandler()
    app_log_handler.setFormatter(app_log_formatter)
    app_logger.addHandler(app_log_handler)
    if log_level >= logging.DEBUG:
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
