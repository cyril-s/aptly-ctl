import logging
import sys
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_remove = subparsers_action_object.add_parser("remove",
            description="Remove packages from local repos and update dependent publishes.",
            help="Remove packages from local repos and update dependent publishes.")
    parser_remove.set_defaults(func=remove)

    parser_remove.add_argument("refs", metavar="repo/package_referece", nargs="*",
            help="""repo is a repo name from where to remove package,
                    and package_reference is either an aplty key of a package
                    (e.g. 'Pi386 libboost-program-options-dev 1.49.0.1 918d2f433384e378')
                    or direct reference (e.g. libboost-program-options-dev_1.49.0.1_i386).
                    If no refs are supplied stdin is read.""")

    parser_remove.add_argument("--dry-run", action="store_true",
            help="Do not delete packages or update publish. Just validate actions and show what is to be done")


def remove(config, args):
    aptly = ExtendedAptlyClient(config.url)
    all_refs = dict()
    input_refs = (r for r in args.refs) if len(args.refs) > 0 else sys.stdin

    # some subcommands return refs wrapped in quotes for convenient copy-pasting
    # so this supports the case when that output is fed to this subcommand
    for r in map(lambda line: line.strip().strip('"\''), input_refs):
        if r == "":
            continue
        ref = PackageRef(r)
        if ref.repo is None:
            raise DidwwAptlyCtlError("Remove subcommand requires that package ref containes repo name")
        elif ref.key is None:
            # we got direct reference, gotta look up hash
            try:
                ref_aptly_key = aptly.search_by_PackageRef(ref, use_ref_repo=True, detailed=False)
            except AptlyAPIException as e:
                if e.status_code == 404:
                    raise DidwwAptlyCtlError("When resolving direct reference '{}' to aptly key repo '{}' was not found".format(ref, ref.repo)) from e
                else:
                    raise
            else:
                if len(ref_aptly_key) != 1:
                    raise DidwwAptlyCtlError("When resolving direct reference '{}' to aptly key API returned: {}".format(ref, ref_aptly_key))
                else:
                    all_refs.setdefault(ref.repo, list()).append(ref_aptly_key[0])
        else:
            all_refs.setdefault(ref.repo, list()).append(ref)

    if not all_refs:
        raise DidwwAptlyCtlError("No reference were supplied. Nothing to remove.")

    failed_repos = []
    for repo, refs in all_refs.items():
        try:
            delete_result = aptly.repos.delete_packages_by_key(repo, *[r.key for r in refs])
        except AptlyAPIException as e:
            logger.error(e)
            logger.debug("", exc_info=True)
            failed_repos.append(repo)
            for r in refs:
                logger.error('Failed to remove "{}" from {}'.format(r, repo))
                print('"' + repr(r) + '"')
        else:
            for r in refs:
                logger.info('Removed "{}" from {}'.format(r, repo))
            logger.debug("API returned: " + str(delete_result))
    else:
        for f in failed_repos:
            del all_refs[f] # no need to update publish sourced from this repo

    if not all_refs:
        raise DidwwAptlyCtlError("Failed to remove anything.")

    update_exceptions = aptly.update_dependent_publishes(all_refs.keys(), config, args.dry_run)
    if len(update_exceptions) > 0:
        raise DidwwAptlyCtlError("Some publishes fail to update")
    else:
        return 0
