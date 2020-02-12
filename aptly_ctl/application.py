import argparse
import logging
import sys
import requests.exceptions
from aptly_ctl import app_logger, __version__, __progName__
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils.Version import system_ver_compare
from aptly_ctl.Config import Config, VERBOSITY
from aptly_api.base import AptlyAPIException
import aptly_ctl.subcommands


def _init_logging(level, subcommand):
    numeric_level = getattr(logging, level, None)
    if level == VERBOSITY[2]:
        log_fmt = "%(levelname)s {}(%(process)d) [%(name)s:%(funcName)s()] %(message)s".format(
            subcommand
        )
    else:
        log_fmt = "%(levelname)s {}(%(process)d) %(message)s".format(subcommand)
    app_logger.setLevel(numeric_level)
    app_formatter = logging.Formatter(fmt=log_fmt)
    app_handler = logging.StreamHandler()
    app_handler.setLevel(numeric_level)
    app_handler.setFormatter(app_formatter)
    app_logger.addHandler(app_handler)
    if level == VERBOSITY[2]:
        urllib3_logger = logging.getLogger("urllib3")
        urllib3_logger.setLevel(numeric_level)
        urllib3_logger.addHandler(app_handler)


def config_parser():

    description = """
    aptly-ctl -- is a convenient aptly API  command line client.  For details on
    aptly see  https://www.aptly.info/.  This tool uses some notations that help
    tool to interact with itself. Here are they.

    package_reference form is  [<repository>/]{<aptly key>, <direct reference>}.

    <aptly key> is in the form "P<arch> <name> <version> <hash>" e.g.
    "Pamd64 aptly 2.2.2 1234567890123456".

    <direct reference> form is "<name>_<arch>_<version>" e.g. aptly_amd64_2.2.2.
    <repository>  is  a local  repo  name  precising packge  location  and it is
    optional.  However some subcommands may require it for correct operation and
    they will mention that.

    If a subcommand needs some particular form of  package_reference  (e.g needs
    only <repository>/<aptly key>), then it states that explicitly.

    PUB_SPEC is in the form "[<storage>:]<prefix>/<distribution>" and it is used
    to  specify   publishes.   See  https://www.aptly.info/doc/api/publish/  for
    details and NOTE, you don't have to substitute '/', '.' and '_' here.

    Various subcommands accept package_references and PUB_SPEC from command line
    or on stdin, and print them on stdout, which allows interaction between them
    through pipe. Subcommands' --help will mention what they print to STDOUT and
    what they can read from STDIN and give you some hints how you can "pipe" it.

    Generally  STDOUT  will be  parsable by other  subcommands  or absent and no
    messages  will  be  printed  to  STDERR  (to  change  this  us  '-v'  flag).
    So no output is a success.\
    """

    parser = argparse.ArgumentParser(
        prog=__progName__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=description,
    )

    parser.add_argument(
        "-p",
        "--profile",
        default="0",
        help="profile from config file. Can be it's name or number. Default is the first one",
    )

    parser.add_argument("-c", "--config", help="path to config file")

    parser.add_argument(
        "-C",
        "--config-keys",
        metavar="KEY",
        action="append",
        default=[],
        help="override key value in config for chosen profile",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase verbosity. Can be set mutiple times to increase verbosity even more",
    )

    parser.add_argument(
        "--version", action="version", version="%(prog)s {}".format(__version__)
    )

    parser.add_argument(
        "--timeout", type=int, default=500, help="read timeout for http requests"
    )

    subparsers = parser.add_subparsers(dest="subcommand")
    return (parser, subparsers)


def main():
    parser, subparsers = config_parser()
    for subcommand in aptly_ctl.subcommands.__all__:
        eval("aptly_ctl.subcommands.%s.config_subparser(subparsers)" % subcommand)

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(2)

    log_level = VERBOSITY[min(args.verbose, len(VERBOSITY) - 1)]
    try:
        _init_logging(log_level, args.subcommand)
    except ValueError as e:
        print(e)
        sys.exit(2)
    logger = logging.getLogger(__name__)

    try:
        config = Config(args.config, args.profile, args.config_keys)
    except AptlyCtlError as e:
        logger.error(e)
        logger.debug("", exc_info=True)
        sys.exit(2)

    if not system_ver_compare:
        logger.debug(
            "Cannot import apt.apt_pkg module from python3-apt"
            + " package. Using python substitute that is much slower."
        )

    logger.info("Running %s subcommand." % args.subcommand)
    try:
        sys.exit(args.func(config, args))
    except AptlyAPIException as e:
        if e.status_code == 404 and "page not found" in e.args[0].lower():
            logger.error(
                "API reponded with '%s'. Check configured API url and run command with -vv to see failed request details."
                % e.args[0]
            )
            logger.debug("", exc_info=True)
            sys.exit(1)
        else:
            raise
    except (AptlyCtlError, requests.exceptions.RequestException) as e:
        logger.error(e)
        logger.debug("", exc_info=True)
        sys.exit(1)
