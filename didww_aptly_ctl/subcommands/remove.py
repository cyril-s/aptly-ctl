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
    aptly = ExtendedAptlyClient(config["url"])
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
        else:
            for r in refs:
                logger.info('Removed "{}" from {}'.format(r, repo))
            logger.debug("API returned: " + str(delete_result))
    else:
        for f in failed_repos:
            del all_refs[f] # no need to update publish sourced from this repo

    if not all_refs:
        raise DidwwAptlyCtlError("Failed to remove anything.")

    pubs = aptly.lookup_publish_by_repos(list(all_refs.keys()))
    update_exceptions = []
    for p in pubs:
        logger.info('Updating publish with prefix "{}", dist "{}"'.format(p.prefix, p.distribution))
        if not args.dry_run:
            try:
                update_result = aptly.publish.update(
                        prefix = p.prefix,
                        distribution = p.distribution,
                        sign_skip = config["signing"]["skip"],
                        sign_batch = config["signing"]["batch"],
                        sign_gpgkey = config["signing"]["gpg_key"],
                        sign_keyring = config["signing"]["keyring"],
                        sign_secret_keyring = config["signing"]["secret_keyring"],
                        sign_passphrase = config["signing"]["passphrase"],
                        sign_passphrase_file = config["signing"]["passphrase_file"],
                        )
            except AptlyAPIException as e:
                logger.error('Can\'t update publish with prefix "{}", dist "{}".'.format(p.prefix,p.distribution))
                update_exceptions.append(e)
                if args.verbose > 1:
                    logger.exception(e)
                else:
                    logger.error(e)
            else:
                logger.debug("API returned: " + str(update_result))
                logger.info('Updated publish with prefix "{}", dist "{}".'.format(p.prefix, p.distribution))

    if len(update_exceptions) > 0:
        raise DidwwAptlyCtlError("Some publishes fail to update")
    else:
        return 0
