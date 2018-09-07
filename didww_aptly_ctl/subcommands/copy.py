import logging
import sys
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_copy = subparsers_action_object.add_parser("copy",
            description="Copy packages between local repos and update dependent publishes.",
            help="Copy packages between local repos and update dependent publishes.")
    parser_copy.set_defaults(func=copy)

    parser_copy.add_argument("--dry-run", action="store_true",
            help="Don't do anything, just show what is to be done")

    parser_copy.add_argument("-t", "--target", required=True,
            help="Target repo name.")

    parser_copy.add_argument("refs", metavar="package_referece", nargs="*",
            help="Package reference. If no refs are supplied stdin is read.")


def copy(config, args):
    aptly = ExtendedAptlyClient(config.url)
    input_refs = iter(args.refs) if len(args.refs) > 0 else sys.stdin
    refs = []

    for r in map(lambda line: line.strip(' \t\r\n"\''), input_refs):
        if r != "":
            refs.append(PackageRef(r).key)

    if not refs:
        raise DidwwAptlyCtlError("No reference were supplied. Nothing to copy.")

    logger.info("Copying {} into {}".format(refs, args.target))
    try:
        if not args.dry_run:
            add_result = aptly.repos.add_packages_by_key(args.target, *refs)
            logger.debug("add result: {}".format(add_result))
    except AptlyAPIException as e:
        if e.status_code in [400, 404]:
            raise DidwwAptlyCtlError(e)
        else:
            raise
    else:
        for r in refs:
            print('"' + repr(PackageRef(r, args.target)) + '"')

    update_exceptions = aptly.update_dependent_publishes([args.target], config, args.dry_run)
    if len(update_exceptions) > 0:
        raise DidwwAptlyCtlError("Some publishes fail to update")
    else:
        return 0
