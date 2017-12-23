import argparse
import logging
import sys
import requests.exceptions
from didww_aptly_ctl.defaults import defaults
from didww_aptly_ctl import app_logger
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.Version import system_ver_compare
import didww_aptly_ctl.plugins

def _init_logging(level):
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError("Invalid log level: %s" % level)

    app_logger.setLevel(numeric_level)

    app_log_format = "%(levelname)s [%(name)s:%(funcName)s()] %(message)s"
    app_formatter = logging.Formatter(fmt=app_log_format)

    app_handler = logging.StreamHandler()
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(app_formatter)

    app_logger.addHandler(app_handler)


def main():
    # main parser
    parser = argparse.ArgumentParser(
            description="Aptly API client with convenient defaults and functions.")
    parser.add_argument("-u", "--url", default=defaults["global"]["url"],
            help="Aptly API endpoint url.")
    parser.add_argument("--pass-file", metavar="<path>",
            default=defaults["publish"]["passphraze_file"],
            help="Path to gpg passphraze file local to aptly server.")
    parser.add_argument("-L", "--log-level",
            choices=["debug", "info", "warn", "error", "critical"],
            default=defaults["global"]["log-level"])
    parser.add_argument("--fmt", choices=["yaml", "json"], default="yaml",
            help="Output format.")

    subparsers = parser.add_subparsers(dest="subcommand")

    # init subparsers
    for plugin in didww_aptly_ctl.plugins.__all__:
        eval("didww_aptly_ctl.plugins.%s.config_subparser(subparsers)" % plugin)

    args = parser.parse_args()

    # init logger
    try:
        _init_logging(args.log_level)
    except ValueError as e:
        print(e)
        sys.exit(1)
    logger = logging.getLogger(__name__)

    if not system_ver_compare:
        logger.debug("Cannot import apt.apt_pkg module from python3-apt" \
                + " package. Using python substitute that is much slower.")

    # run subcommand
    if not args.subcommand:
        parser.print_help()
    else:
        logger.info("Running %s plugin." % args.subcommand)
        try:
            sys.exit(args.func(args))
        except DidwwAptlyCtlError as e:
            exc_logger = getattr(e, "logger", logger)
            if args.log_level.upper() == "DEBUG":
                exc_logger.exception(e.msg)
            else:
                exc_logger.error(e.msg)
            sys.exit(1)
        except requests.exceptions.ConnectionError as e:
            if args.log_level.upper() == "DEBUG":
                logger.exception(e)
            else:
                logger.error(e)
            sys.exit(1)


