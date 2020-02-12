import logging
import sys
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_api.base import AptlyAPIException
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)


def config_subparser(subparsers_action_object):
    parser_copy = subparsers_action_object.add_parser(
        "copy",
        help="copy packages between local repos",
        description="""
            Copy packages between local repos and update dependent publishes.
            STDOUT is a new package_references of the form <repository>/<aptly key>
            in target repo. You can pipe it to remove subcommand to delete them
            immediately or to copy subcommand to copy them again.
            """,
    )
    parser_copy.set_defaults(func=copy)

    parser_copy.add_argument(
        "--dry-run",
        action="store_true",
        help="don't do anything, just show what is to be done",
    )

    parser_copy.add_argument("-t", "--target", required=True, help="target repo name.")

    parser_copy.add_argument(
        "keys",
        metavar="<repository>/<aptly key>",
        nargs="*",
        help="aptly key with local repo name (see 'aplty-ctl --help'). If no keys are supplied stdin is read",
    )


def copy(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    input_refs = iter(args.keys) if len(args.keys) > 0 else sys.stdin
    refs = []

    for r in map(lambda line: line.strip(" \t\r\n\"'"), input_refs):
        if r != "":
            p = PackageRef(r)
            try:
                key = p.key
            except TypeError as e:
                raise AptlyCtlError('Incorrect aptly key "{}": {}'.format(r, e))
            refs.append(key)

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

    update_exceptions = aptly.update_dependent_publishes(
        [args.target], config, args.dry_run
    )
    if len(update_exceptions) > 0:
        raise AptlyCtlError("Some publishes fail to update")
    else:
        return 0
