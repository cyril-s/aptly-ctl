import logging
import json
import sys
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import publish_update

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    descr_msg = """
    Remove packages from local repos.
    """
    parser_remove = subparsers_action_object.add_parser("remove",
        description=descr_msg,
        help="Removes packages from local repos.")
    parser_remove.set_defaults(func=remove)
    parser_remove.add_argument("-r", "--repo",
            help="Repo name from where to remove packages.")
    group = parser_remove.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--file",
            help="""Read instructions from file (- for stdin).
            Format is json dictionary of repo names as keys, and
            aptly packages keys list as values.""")
    group.add_argument("-R", "--refs", metavar="ref", nargs='+',
            help="""Direct refereces to package or aptly keys.
            E.g. didww-panel-api_3.16.2~rc1_amd64 or
            "Pamd64 didww-panel-api 3.16.2~rc1 54ecb10fabbd98bf"
            """)


def remove(args):
    aptly = Client(args.url)
    if args.file:
        if args.file == "-":
            try:
                remove_list = json.load(sys.stdin)
            except json.JSONDecodeError as e:
                raise DidwwAptlyCtlError("Cannot load from stdin:", e)
        else:
            try:
                with open(args.file, "r") as f:
                    remove_list = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                raise DidwwAptlyCtlError("Cannot load from file -f:", e)
    elif args.refs:
        if not args.repo:
            raise DidwwAptlyCtlError("You have to specify --repo for -R option.")
        else:
            remove_list = {args.repo: args.refs}

    if len(remove_list) == 0:
        logger.warn("Nothing to remove.")
        return 0

    pubs_to_update = set()
    for repo, keys in remove_list.items():
        pubs_to_update.add(repo.split("_")[0])
        for key in keys:
            logger.info(''.join(["    ", '"', key, '"']))
        logger.info("Removing packages above from %s" % repo)
        try:
            aptly.repos.delete_packages_by_key(repo, *keys)
        except AptlyAPIException as e:
            if args.cont and e.status_code == 404:
                logger.error("Failed to delete packages: %s" % e)
            elif not args.cont and e.status_code == 404:
                raise DidwwAptlyCtlError("Failed to delete packages.", e)
            else:
                raise

    # Update publish
    for pub in pubs_to_update:
        update_result = publish_update(aptly, pub, pub, args.pass_file)
        logger.debug(update_result)
        logger.info("Updated publish {0}/{0}".format(pub))

    return 0

