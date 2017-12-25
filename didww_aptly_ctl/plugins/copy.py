"""
Uses aptly-api-client (https://github.com/gopythongo/aptly-api-client)
"""

import logging
from re import match
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import lookup_publish_by_repos, flatten_list
from didww_aptly_ctl.defaults import defaults
from didww_aptly_ctl.utils import AptlyKey
from didww_aptly_ctl.utils import SerializedIO

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    desc_msg = """
    Copies/moves packages between local repos and updates dependent publishes.
    Outputs a dict with target repo as key, and list of successfully copied
    packages as value. By default, works in the mode 'copy all valid or nothing'.
    With -k prints warnings, but performs valid actions.
    Flag -f allows to copy between repos with different default distributions.
    """
    help_msg = """
    Copies/Moves packages between local repos and updates dependent publishes
    """
    parser_copy = subparsers_action_object.add_parser("copy", description=desc_msg, help=help_msg)

    parser_copy.set_defaults(func=copy)

    help_msg = """
    Target repo name. E.g. --target jessie_billing_stable
    """
    parser_copy.add_argument("-t", "--target", required=True, help=help_msg)

    help_msg = """
    source_repo is a repo name from where to copy package, and package_reference is an
    aplty key of a package (e.g. 'Pi386 libboost-program-options-dev 1.49.0.1 918d2f433384e378').
    If '-' is supplied, reads a source refs list from stdin in a form of
    a dictionary, where keys are repo names, and values are lists of aptly
    keys (e.g. read output of search plugin)
    """
    parser_copy.add_argument("refs", metavar="source_repo/package_referece", nargs="+", help=help_msg)

    help_msg = "Remove packages from source"
    parser_copy.add_argument("-m", "--move", action="store_true", help=help_msg)

    help_msg = "Keep going even if errors occur"
    parser_copy.add_argument("-k", "--keep-going", action="store_true", help=help_msg)

    help_msg = "Allow copy when the default distribution of a source and a target do not match"
    parser_copy.add_argument("-f", "--force", action="store_true", help=help_msg)

    help_msg = "Don not copy, delete or update publish. Just validate actions and show is to be done"
    parser_copy.add_argument("--dry-run", action="store_true", help=help_msg)


def get_repo_info(client, repo):
    try:
        return client.repos.show(repo)
    except AptlyAPIException as e:
        if e.status_code == 404:
            raise DidwwAptlyCtlError("Repo '{}' doest not exist".format(args.target))
        else:
            raise


def copy(args):
    aptly = Client(args.url)
    io = SerializedIO(input_f='stdin', output_f='stdout', output_f_fmt=args.fmt)

    # construct source refs dict
    if args.refs[0] == "-":
        logger.info("Getting source refs from stdin")
        source_refs = io.get_input()
    else:
        source_refs = dict()
        for r in args.refs:
            repo, _, ref = r.partition("/")
            if ref == "":
                raise DidwwAptlyCtlError("Incorrect source reference name: '{}'".format(r))
            elif repo in source_refs:
                source_refs[repo].append(ref)
            else:
                source_refs[repo] = [ ref ]

    if source_refs is None or len(source_refs) == 0:
        raise DidwwAptlyCtlError("Source list is empty")

    # check for invalid actions
    errors = False
    target_repo = get_repo_info(aptly, args.target)
    logger.debug("Source refs before validation: {}".format(source_refs))
    for repo, refs in source_refs.copy().items():
        try:
            repo_info = get_repo_info(aptly, repo)
            if not args.force and repo_info.default_distribution != target_repo.default_distribution:
                raise DidwwAptlyCtlError("Default distributions of the source repo " \
                        + "'{}', '{}'".format(repo_info.name, repo_info.default_distribution) \
                        + " does not match one of the target repo " \
                        + "'{}', '{}'.".format(target_repo.name, target_repo.default_distribution) \
                        + " Supply --force to ignore this")
        except DidwwAptlyCtlError as e:
            logger.warn(e)
            erros = True
            del source_refs[repo]
            break
        for ref in refs[:]:
            key = AptlyKey(ref, repo)
            if not key.exists(aptly):
                logger.warn("There is no '{}' in '{}'".format(ref, repo))
                erros = True
                source_refs[repo].remove(ref)
    logger.debug("Source refs after validation: {}".format(source_refs))

    if errors and not args.keep_going:
        raise DidwwAptlyCtlError("There are invalid actions. Invoke with --keep-going to do valid actions.")
    elif errors and args.keep_going:
        logger.warn("Skipping invalid actions...")
    if len(source_refs) == 0: 
        raise DidwwAptlyCtlError("There are no valid actions.")

    # Copy packages
    keys = flatten_list(source_refs.values())
    keys.sort(key=lambda key: AptlyKey(key))
    logger.debug("keys to copy: {}".format(keys))

    #TODO handle case when some of pakcages connot be copied because of conflict
    try:
        if not args.dry_run:
            add_result = aptly.repos.add_packages_by_key(args.target, *keys)
            logger.debug("add result: {}".format(add_result))
    except AptlyAPIException as e:
        if e.status_code == 400:
            raise DidwwAptlyCtlError("Failed to copy packages", e)
        else:
            raise

    # Delete source if --move
    if args.move:
        for repo, refs in source_refs.items():
            logger.debug("deleting {} from {}".format(refs, repo))
            if not args.dry_run:
                delete_result = aptly.repos.delete_packages_by_key(repo, *refs)
                logger.debug("delete result: {}".format(delete_result))

    # Update publishes
    pubs = lookup_publish_by_repos(aptly, list(source_refs.keys()) + [target_repo.name])
    for p in pubs:
        if not args.dry_run:
            update_result = aptly.publish.update(
                    prefix = p.prefix,
                    distribution = p.distribution,
                    sign_gpgkey = defaults["publish"]["gpg_key_name"],
                    sign_passphrase_file = defaults["publish"]["passphraze_file"]
                    )
            logger.debug(update_result)
        logger.info("Updated publish {}/{}".format(p.prefix, p.distribution))

    io.print_output({args.target: keys})
    return 0

