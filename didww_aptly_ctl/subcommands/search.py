import logging
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_search = subparsers_action_object.add_parser("search",
            help="Search packages in local repos.",
            description="Search packages in local repos.")
    parser_search.set_defaults(func=search)

    parser_search.add_argument("queries", metavar="query", nargs="+",
            help="Query in format documented at https://www.aptly.info/doc/feature/query/.")

    parser_search.add_argument("-r", "--repo", dest="repos", action="append",
            help="Limit search to specified repos.")

    #parser_search.add_argument("-n", "--name", action="store_true",
    #        help="Treat query as regex of package's name.")

    #parser_search.add_argument("--pretty", action="store_true",
    #        help="Print more readable rather than parsable output.")


def search(config, args):
    aptly = ExtendedAptlyClient(config["url"])

    if args.repos:
        repo_list = args.repos[:]
    else:
        search_result = aptly.repos.list()
        repo_list = [ r[0] for r in search_result ]
        if len(repo_list) == 0:
            raise DidwwAptlyCtlError("Seems aptly doesn't have any local repos.")
    logger.info("Searching in repos {}".format(", ".join(repo_list)))
    repo_list.sort()

    try:
        for q in args.queries:
            logger.debug("Query: " + q)
            for r in repo_list:
                search_result = aptly.repos.search_packages(r, q)
                searched_list = [ s.key for s in search_result ]
                logger.debug("For query '{}' in repo '{}' api returned: {}".format(q, r, search_result))
                searched_list.sort(key=lambda key: PackageRef(key))
                for s in searched_list:
                    # print quotes too for convenient copy-pasting in terminal
                    print('"{}/{}"'.format(r, s))
    except AptlyAPIException as e:
        if e.status_code in [404, 400]:
            raise DidwwAptlyCtlError("Failed to search packages.", e)
        else:
            raise

    return 0
