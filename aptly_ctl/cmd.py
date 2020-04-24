import argparse
import logging
from typing import Iterable, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from aptly_ctl import VERSION
from aptly_ctl.aptly import Client, Repo, Snapshot, search
from aptly_ctl.config import Config, parse_override_dict
from aptly_ctl.exceptions import AptlyApiError

log = logging.getLogger(__name__)

PACKAGE_QUERY_DOC_URL = "https://www.aptly.info/doc/feature/query/"


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

    version_subcommand = subcommands.add_parser(
        "version", help="show aptly server version"
    )
    version_subcommand.set_defaults(func=version)

    package_subcommand = subcommands.add_parser(
        "package", help="search packages and show info about them"
    )
    package_actions = package_subcommand.add_subparsers(dest="action")

    package_show_action = package_actions.add_parser("show", help="show package info")
    package_show_action.set_defaults(func=package_show)
    package_show_action.add_argument(
        "query", help="package query. For query syntax see " + PACKAGE_QUERY_DOC_URL,
    )

    package_search_action = package_actions.add_parser("search", help="search packages")
    package_search_action.set_defaults(func=package_search)
    package_search_action.add_argument(
        "queries",
        metavar="[ query ... ]",
        nargs="*",
        help="package queries. Multiple queries are ORed. For query syntax see "
        + PACKAGE_QUERY_DOC_URL,
    )
    package_search_action.add_argument(
        "--with-deps",
        action="store_true",
        help="include dependencies when evaluating package query",
    )
    package_search_action.add_argument("--format", dest="fmt", help="output format")

    args = parser.parse_args()

    if not args.subcommand:
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

    args.func(aptly, **vars(args))


def version(aptly: Client, **kwargs: Any) -> None:
    print(aptly.version())


def package_show(aptly: Client, query: str, **kwargs: Any) -> None:
    print(aptly.package_show(key))


def package_search(
    aptly: Client,
    queries: Iterable[str],
    with_deps: bool,
    fmt: str,
    max_workers: int,
    **kwargs: Any
) -> None:
    fmt = "{s.name} {p.key}"
    if not queries:
        queries = ("",)
    result, errors = search(aptly, queries, max_workers=max_workers)
    for store, packages in result:
        for package in packages:
            print(fmt.format(s=store, p=package))
    for error in errors:
        log.error(error)
