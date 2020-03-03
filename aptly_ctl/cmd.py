import argparse
import logging
from typing import Any
from aptly_ctl import VERSION
from aptly_ctl.aptly import Client
from aptly_ctl.config import Config, parse_override_dict

log = logging.getLogger(__name__)


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
        help="provide value for configuration KEY. Takes precedence over config file. Use dots to set nested fields e.g. signing.gpgkey=somekey",
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    version_parser = subparsers.add_parser("version", help="show aptly server version")
    version_parser.set_defaults(func=version)

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


def version(aptly: Client, **other_args: Any) -> None:
    print(aptly.version())
