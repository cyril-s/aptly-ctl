import logging
import json
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.utils.misc import search_package_in_repo
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils import SerializedIO, AptlyKey

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    descr_msg = """
    Search package in Aptly repo. If query_string is specified, -n, -v, -a options are ignored.
    If no option is specified, lists all packages in all repos.
    -n, -v and -a options are ANDed.
    STDOUT: dictionary of repos names as keys and found keys list as values serialized in specified format.
    query_string format docs - https://www.aptly.info/doc/feature/query/.
    """
    parser_search = subparsers_action_object.add_parser("search",
            description=descr_msg, help="Search packages.")
    parser_search.set_defaults(func=search)
    #TODO select multiples repos and support wildcards/regexps
    parser_search.add_argument("-r", "--repo", help="Limit search to specified repos.")
    parser_search.add_argument("-n", "--name",
            help="Name of package to search for. Can be wildcard ('[^]?*' symbols)")
    parser_search.add_argument("-v", "--version",
            help="Version of package to search for. Version filed is searched  by " \
                  + "operators >=, <=, =, >>, << according to apt rules. Operator must " \
                  + "precede version (e.g. '>=1.0.1' or '>= 1.0.1'). If not, default is '='.")
    parser_search.add_argument("-a", "--arch",
            help="Architecture of package to search for. Can be wildcard ('[^]?*' symbols)")
    #TODO parser_search.add_argument("-R", help="Treat -n, -v, -a options as regexp.")
    parser_search.add_argument("query_string", nargs='?', default=None,
            help="Query string that is passed directly to Aptly API.")


def search(args):
    aptly = Client(args.url)
    repo = getattr(args, "repo", None)
    io = SerializedIO(input_f='stdin', output_f='stdout', output_f_fmt=args.fmt)

    # Make repo list 
    if repo is None:
        search_result = aptly.repos.list()
        repo_list = [ r[0] for r in search_result ]
        if len(repo_list) == 0:
            raise DidwwAptlyCtlError("Seems aptly doesn't have any local repos.")
    else:
        repo_list = [ repo ]
    logger.info("Searching in repos {}".format(", ".join(repo_list)))

    # Compile query
    if args.query_string:
        query = args.query_string
    else:
        query = dict()
        for attr in ["name", "version", "architecture"]:
            if hasattr(args, attr):
                query[attr] = getattr(args, attr)
    logger.debug("Query is %s" % query)

    # Search
    repo_list.sort()
    result = dict()
    try:
        for r in repo_list:
            if isinstance(query, str):
                search_result = aptly.repos.search_packages(r, query)
                searched_list = [ s[0] for s in search_result ]
            else:
                searched_list = search_package_in_repo(aptly, r, **query)

            if len(searched_list) != 0:
                result[r] = sorted(searched_list, key=lambda key: AptlyKey(key))
    except AptlyAPIException as e:
        if e.status_code in [404, 400]:
            raise DidwwAptlyCtlError("Failed to search packages.", e)
        else:
            raise

    io.print_output(result)
    return 0

