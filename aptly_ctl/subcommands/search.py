import logging
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_api.base import AptlyAPIException
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_search = subparsers_action_object.add_parser("search",
            help="Search packages in local repos.",
            description="Search packages in local repos.")
    parser_search.set_defaults(func=search)

    parser_search.add_argument("queries", metavar="query", nargs="*",
            help="Query in format documented at https://www.aptly.info/doc/feature/query/."
                 " No query means list everything.")

    parser_search.add_argument("-r", "--repo", dest="repos", action="append",
            help="Limit search to specified repos.")

    parser_search.add_argument("-n", "--name", action="store_true",
            help="Treat query as regex of package's name.")

    #TODO
    #parser_search.add_argument("--pretty", action="store_true",
    #        help="Print more readable rather than parsable output.")

    parser_search.add_argument("--with-deps", action="store_true",
            help="Include dependencies (that are in the same repo)  when evaluating package query.")

    parser_search.add_argument("--details", action="store_true",
            help="Return full information about each package (might be slow on large repos).")

    parser_search.add_argument("--rotate", type=int, metavar="N",
            help="N is a number of latest package versions to omit when printing a result. "
                 "Output can be piped to remove subcommand to delete old versions. "
                 "If N is negative, N latest packages would be shown.")


def rotate(packages, n):
    h = {}
    for p in packages:
        ref = PackageRef(p.key)
        h.setdefault("{}{}{}".format(ref.prefix, ref.arch, ref.name), []).append(p)
    for k, v in h.items():
        v.sort(key=lambda s: PackageRef(s.key))
        h[k] = v[:len(v)-n] if n >= 0 else v[len(v)+n:]
    result = []
    for a in h.values():
        result += a
    return result


def search(config, args):
    aptly = ExtendedAptlyClient(config.url)
    if not args.queries:
        args.queries.append("")

    if args.repos:
        repo_list = args.repos[:]
    else:
        search_result = aptly.repos.list()
        repo_list = [ r[0] for r in search_result ]
        if len(repo_list) == 0:
            raise AptlyCtlError("Seems aptly doesn't have any local repos.")
    repo_list.sort()
    logger.info("Searching in repos {}".format(", ".join(repo_list)))

    for q in args.queries:
        if args.name:
            q = "Name (~ {})".format(q)
        logger.info("Query: " + q)
        for r in repo_list:
            try:
                search_result = aptly.repos.search_packages(r, q, args.with_deps, args.details)
            except AptlyAPIException as e:
                if e.status_code == 404:
                    raise AptlyCtlError(e) from e
                else:
                    raise
            logger.debug("For query '{}' in repo '{}' api returned: {}".format(q, r, search_result))
            if args.rotate:
                search_result = rotate(search_result, args.rotate)
            search_result.sort(key=lambda s: PackageRef(s.key))
            for s in search_result:
                # print quotes too for convenient copy-pasting in terminal
                print('"{}/{}"'.format(r, s.key))
                if args.details:
                    for k, v in s.fields.items():
                        print(" "*4 + "{}: {}".format(k, v))

    return 0