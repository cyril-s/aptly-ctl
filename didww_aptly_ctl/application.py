import argparse
import logging
import sys
import requests.exceptions
from didww_aptly_ctl.defaults import defaults, VERBOSITY
from didww_aptly_ctl import app_logger, __version__, __progName__
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.Version import system_ver_compare
import didww_aptly_ctl.plugins

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
    # main parser
    parser = argparse.ArgumentParser(prog=__progName__,
            description="Aptly API client with convenient defaults and functions.")

    parser.add_argument("-u", "--url", default=defaults["global"]["url"],
            help="Aptly API endpoint url")

    parser.add_argument("--pass-file", metavar="<path>", dest="pass_file_path",
            default=defaults["publish"]["passphraze_file"],
            help="Path to gpg passphraze file local to aptly server")

    parser.add_argument("--gpg-key", metavar="<name>", dest="gpg_key_name",
            default=defaults["publish"]["gpg_key_name"],
            help="gpg key name (local to aptly server/user)")

    parser.add_argument("-v", "--verbose", action="count", default=0,
            help="Increase verbosity")

    parser.add_argument("--fmt", choices=["yaml", "json"], default="yaml",
            help="Output format")

    parser.add_argument("--version", action="version", version="%(prog)s {}".format(__version__))

    subparsers = parser.add_subparsers(dest="subcommand")

    # init subparsers
    for plugin in didww_aptly_ctl.plugins.__all__:
        eval("didww_aptly_ctl.plugins.%s.config_subparser(subparsers)" % plugin)

    args = parser.parse_args()

    # set up logging
    try:
        log_level = VERBOSITY[args.verbose]
    except IndexError:
        log_level = "DEBUG"

    try:
        _init_logging(log_level)
    except ValueError as e:
        print(e)
        sys.exit(1)
    logger = logging.getLogger(__name__)

    # check version comparios from python3-apt module
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
        except (DidwwAptlyCtlError, requests.exceptions.ConnectionError) as e:
            logger.error(e)
            logger.debug("", exc_info=True)
            sys.exit(1)
