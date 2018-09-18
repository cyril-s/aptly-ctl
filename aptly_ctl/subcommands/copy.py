import logging
import sys
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_api.base import AptlyAPIException
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_copy = subparsers_action_object.add_parser("copy",
            help="copy packages between local repos",
            description="""
            Copy packages between local repos and update dependent publishes.
            STDOUT is new package_references in target repo. You can pipe it to
            remove subcommand to delete them immediately or to copy subcommand
            to copy them again.
            """)
    parser_copy.set_defaults(func=copy)

    parser_copy.add_argument("--dry-run", action="store_true",
            help="don't do anything, just show what is to be done")

    parser_copy.add_argument("-t", "--target", required=True,
            help="target repo name.")

    parser_copy.add_argument("refs", metavar="package_referece", nargs="*",
            help="package reference (see 'aplty-ctl --help'). If no refs are supplied stdin is read")


def copy(config, args):
    aptly = ExtendedAptlyClient(config.url)
    input_refs = iter(args.refs) if len(args.refs) > 0 else sys.stdin
    refs = []

    for r in map(lambda line: line.strip(' \t\r\n"\''), input_refs):
        if r != "":
            refs.append(PackageRef(r).key)

    if not refs:
        raise AptlyCtlError("No reference were supplied. Nothing to copy.")

    logger.info("Copying {} into {}".format(refs, args.target))
    try:
        if not args.dry_run:
            add_result = aptly.repos.add_packages_by_key(args.target, *refs)
            logger.debug("add result: {}".format(add_result))
    except AptlyAPIException as e:
        if e.status_code in [400, 404]:
            raise AptlyCtlError(e) from e
        else:
            raise
    else:
        for r in refs:
            print('"' + repr(PackageRef(args.target + "/" + r)) + '"')

    update_exceptions = aptly.update_dependent_publishes([args.target], config, args.dry_run)
    if len(update_exceptions) > 0:
        raise AptlyCtlError("Some publishes fail to update")
    else:
        return 0
