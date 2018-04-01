import logging
import json
import sys
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils import SerializedIO
from didww_aptly_ctl.utils.misc import lookup_publish_by_repos, flatten_list
from didww_aptly_ctl.defaults import defaults

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    descr_msg = "Remove packages from local repos and update dependent publishes."
    help_msg =  "Remove packages from local repos and update dependent publishes."
    parser_remove = subparsers_action_object.add_parser("remove", description=descr_msg, help=help_msg)
    parser_remove.set_defaults(func=remove)

    help_msg = """
    repo is a repo name from where to remove package, and package_reference is an
    aplty key of a package (e.g. 'Pi386 libboost-program-options-dev 1.49.0.1 918d2f433384e378').
    If '-' is supplied, reads a source refs list from stdin in a form of
    a dictionary, where keys are repo names, and values are lists of aptly
    keys (e.g. read output of search plugin)
    """
    parser_remove.add_argument("refs", metavar="repo/package_referece", nargs="+", help=help_msg)

    help_msg = "Don no delete packages or update publish. Just validate actions and show what is to be done"
    parser_remove.add_argument("--dry-run", action="store_true", help=help_msg)


def remove(args):
    aptly = Client(args.url)
    io = SerializedIO(input_f='stdin', output_f='stdout', output_f_fmt=args.fmt)

    # construct source refs dict
    if len(args.refs) == 1 and args.refs[0] == "-":
        logger.info("Getting source refs from stdin")
        refs = io.get_input()
    else:
        refs = dict()
        for r in args.refs:
            repo, sep, ref = r.partition("/")
            if len(sep) == 0:
                raise DidwwAptlyCtlError("Incorrect reference name. '/' is absent: '%s'" % r)
            elif len(sep) > 0 and len(repo) == 0:
                raise DidwwAptlyCtlError("Incorrect reference name. repo is absent: '%s'" % r)
            elif len(sep) > 0 and len(ref) == 0:
                raise DidwwAptlyCtlError("Incorrect reference name. package_referece is absent: '%s'" % r)
            else:
                if repo not in refs:
                    refs[repo] = []
                refs[repo].append(ref)

    if not refs:
        raise DidwwAptlyCtlError("No reference were supplied. Nothing to remove.")

    # remove packages
    failed_repos = []
    for repo, keys in refs.items():
        try:
            delete_result = aptly.repos.delete_packages_by_key(repo, *keys)
        except AptlyAPIException as e:
            if args.verbose > 1:
                logger.exception(e)
            else:
                logger.error(e)
            failed_repos.append(repo)
            for key in keys:
                logger.error('Failed to remove "{}" from {}'.format(key, repo))
        else:
            for key in keys:
                logger.info('Removed "{}" from {}'.format(key, repo))
            logger.debug("API returned: " + str(delete_result))
    else:
        for f in failed_repos:
            del refs[f] # no need to update publish sourced from this repo

    if not refs:
        raise DidwwAptlyCtlError("Failed to remove anything.")

    # Update publishes
    pubs = lookup_publish_by_repos(aptly, list(refs.keys()))
    update_exceptions = []
    for p in pubs:
        logger.info('Updating publish with prefix "{}", dist "{}"'.format(p.prefix, p.distribution))
        if not args.dry_run:
            try:
                update_result = aptly.publish.update(
                    prefix = p.prefix,
                    distribution = p.distribution,
                    sign_gpgkey = args.gpg_key_name,
                    sign_passphrase_file = args.pass_file_path 
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

