import logging
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_api.base import AptlyAPIException
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)


def config_subparser(subparsers_action_object):
    parser_search = subparsers_action_object.add_parser(
        "search",
        help="search packages in local repos",
        description="""
            Search packages in local repos and print found package_references to STDOUT.
            Output can be piped to copy or reomove subcommands. Use --rotate flag and pipe
            STDOUT to remove subcommand to delete old versions of packages from your repo.
            """,
    )
    parser_search.set_defaults(func=search)

    parser_search.add_argument(
        "queries",
        metavar="query",
        nargs="*",
        help="query in format documented at https://www.aptly.info/doc/feature/query/."
        " No query means list everything.",
    )

    parser_search.add_argument(
        "-r",
        "--repo",
        dest="repos",
        action="append",
        help="limit search to specified repos. Can be specified multiple times",
    )

    parser_search.add_argument(
        "-n",
        "--name",
        action="store_true",
        help="treat query as regex of package's name",
    )

    # TODO
    # parser_search.add_argument("--pretty", action="store_true",
    #        help="Print more readable rather than parsable output.")

    parser_search.add_argument(
        "--with-deps",
        action="store_true",
        help="include dependencies (that are in the same repo) when evaluating package query",
    )

    parser_search.add_argument(
        "--details",
        action="store_true",
        help="return full information about each package (might be slow on large repos)",
    )

    parser_search.add_argument(
        "--rotate",
        type=int,
        metavar="N",
        help="N is a number of latest package versions to omit when printing a result. "
        "Output can be piped to remove subcommand to delete old versions. "
        "If N is negative, N latest packages would be shown",
    )

    parser_search.add_argument(
        "--dir-refs", action="store_true", help="print direct references in stdout"
    )


def rotate(packages, n):
    h = {}
    for p in packages:
        ref = PackageRef(p.key)
        h.setdefault("{}{}{}".format(ref.prefix, ref.arch, ref.name), []).append(p)
    for k, v in h.items():
        v.sort(key=lambda s: PackageRef(s.key))
        h[k] = v[: len(v) - n] if n >= 0 else v[len(v) + n :]
    result = []
    for a in h.values():
        result += a
    return result


def search(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    if not args.queries:
        args.queries.append("")

    if args.repos:
        repo_list = args.repos[:]
    else:
        search_result = aptly.repos.list()
        repo_list = [r[0] for r in search_result]
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
                search_result = aptly.repos.search_packages(
                    r, q, args.with_deps, args.details
                )
            except AptlyAPIException as e:
                if e.status_code == 404:  # local repo not found
                    raise AptlyCtlError(e) from e
                elif e.status_code == 400 and "parsing failed:" in e.args[0].lower():
                    _, _, parsing_fail_description = e.args[0].partition(":")
                    raise AptlyCtlError(
                        'Bad query "{}": {}'.format(q, parsing_fail_description.strip())
                    )
                else:
                    raise
            logger.debug(
                "For query '{}' in repo '{}' api returned: {}".format(
                    q, r, search_result
                )
            )
            if args.rotate:
                search_result = rotate(search_result, args.rotate)
            search_result.sort(key=lambda s: PackageRef(s.key))
            for s in search_result:
                # print quotes too for convenient copy-pasting in terminal
                if args.dir_refs:
                    print('"{}/{}"'.format(r, PackageRef(s.key).dir_ref))
                else:
                    print('"{}/{}"'.format(r, s.key))
                if args.details:
                    for k, v in s.fields.items():
                        print(" " * 4 + "{}: {}".format(k, v))

    return 0
