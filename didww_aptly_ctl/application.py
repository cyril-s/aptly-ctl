import argparse
import logging
import sys
import requests.exceptions
from didww_aptly_ctl import app_logger, __version__, __progName__
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.Version import system_ver_compare
from didww_aptly_ctl.Config import Config, VERBOSITY
import didww_aptly_ctl.subcommands

def _init_logging(level):
    numeric_level = getattr(logging, level, None)
    app_logger.setLevel(numeric_level)

    if level == VERBOSITY[2]:
        app_formatter = logging.Formatter(
                fmt="%(levelname)s [%(name)s:%(funcName)s()] %(message)s")
    else:
        app_formatter = logging.Formatter(
                fmt="%(levelname)s %(message)s")

    app_handler = logging.StreamHandler()
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(app_formatter)

    app_logger.addHandler(app_handler)


def main():
    parser = argparse.ArgumentParser(prog=__progName__,
            description="Convenient Aptly API client.")

    parser.add_argument("-p", "--profile", default="0",
            help="Profile from config file. Can be it's name or number. Default is first one.")

    parser.add_argument("-c", "--config",
            help="Path to config file. Default is $HOME/.config/aptly-ctl.conf, "
                 "and then /etc/aptly-ctl.conf")

    parser.add_argument("-C", "--config-keys", metavar="KEY", action="append", default=[],
            help="Override key value in config for chosen profile.")

    parser.add_argument("-v", "--verbose", action="count", default=0,
            help="Increase verbosity")

    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))

    subparsers = parser.add_subparsers(dest="subcommand")

    # init subparsers
    for subcommand in didww_aptly_ctl.subcommands.__all__:
        eval("didww_aptly_ctl.subcommands.%s.config_subparser(subparsers)" % subcommand)

    args = parser.parse_args()

    # set up logging
    log_level = VERBOSITY[min(args.verbose, len(VERBOSITY) - 1)]
    try:
        _init_logging(log_level)
    except ValueError as e:
        print(e)
        sys.exit(1)
    logger = logging.getLogger(__name__)

    # init config
    try:
        config = Config(args.config, args.profile, args.config_keys)
    except DidwwAptlyCtlError as e:
        logger.error(e)
        logger.debug("", exc_info=True)
        sys.exit(127)

    # check version comparios from python3-apt module
    if not system_ver_compare:
        logger.debug("Cannot import apt.apt_pkg module from python3-apt" \
                + " package. Using python substitute that is much slower.")

    # run subcommand
    if not args.subcommand:
        parser.print_help()
    else:
        logger.info("Running %s subcommand." % args.subcommand)
        try:
            sys.exit(args.func(config, args))
        except (DidwwAptlyCtlError, requests.exceptions.RequestException) as e:
            logger.error(e)
            logger.debug("", exc_info=True)
            sys.exit(128)
