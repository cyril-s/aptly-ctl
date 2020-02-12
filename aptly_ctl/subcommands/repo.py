import logging
from pprint import pprint
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_ctl.exceptions import AptlyCtlError
from aptly_api.base import AptlyAPIException
from aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)


def config_subparser(subparsers_action_object):
    parser_repo = subparsers_action_object.add_parser(
        "repo", help="administer local repos", description="Administer local repos."
    )
    subparsers = parser_repo.add_subparsers()

    parser_list = subparsers.add_parser(
        "list", help="list local repos", description="List local repos names to STDOUT."
    )
    parser_list.set_defaults(func=list)
    parser_list.add_argument(
        "--detail",
        action="store_true",
        help="print additional details when showing and listing",
    )

    parser_create = subparsers.add_parser(
        "create", help="create a local repo", description="Create a local repo."
    )
    parser_create.set_defaults(func=create)
    parser_create.add_argument("name", help="name of a new repo")
    parser_create.add_argument(
        "--comment", help="text describing local repository for a user"
    )
    parser_create.add_argument(
        "--dist", help="default distribution when publishing from this local repo"
    )
    parser_create.add_argument(
        "--comp", help="default component when publishing from this local repo"
    )

    parser_edit = subparsers.add_parser(
        "edit", help="edit a local repo", description="Edit a local repo."
    )
    parser_edit.set_defaults(func=edit)
    parser_edit.add_argument("name", help="name of a repo")
    parser_edit.add_argument(
        "--comment", help="text describing local repository for a user"
    )
    parser_edit.add_argument(
        "--dist", help="default distribution when publishing from this local repo"
    )
    parser_edit.add_argument(
        "--comp", help="default component when publishing from this local repo"
    )

    parser_delete = subparsers.add_parser(
        "delete", help="delete a local repo", description="Delete a local repo."
    )
    parser_delete.set_defaults(func=delete)
    parser_delete.add_argument("name", help="name of a repo")
    parser_delete.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="delete local repository even if it has snapshots",
    )


def pprint_repo(repo, packages=[]):
    print(repo.name)
    print("    Default distribution: " + repo.default_distribution)
    print("    Default component: " + repo.default_component)
    print("    Comment: " + repo.comment)
    if packages:
        print("    Packages:")
        packages.sort(key=lambda p: PackageRef(p.key))
        for p in packages:
            print(" " * 8 + '"%s"' % p.key)


def list(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    repo_list = aptly.repos.list()
    repo_list.sort(key=lambda k: k.name)
    for r in repo_list:
        if args.detail:
            pprint_repo(r)
        else:
            print(r.name)
    return 0


def create(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    try:
        create_result = aptly.repos.create(
            args.name, args.comment, args.dist, args.comp
        )
    except AptlyAPIException as e:
        if e.status_code == 400:
            raise AptlyCtlError(e) from e
        else:
            raise
    else:
        logger.info("Created repo {}".format(create_result))
        return 0


def edit(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    try:
        edit_result = aptly.repos.edit(args.name, args.comment, args.dist, args.comp)
    except AptlyAPIException as e:
        if e.status_code in [0, 404]:
            raise AptlyCtlError(e) from e
        else:
            raise
    else:
        logger.info("Edited repo: {}".format(edit_result))
        return 0


def delete(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    try:
        aptly.repos.delete(args.name, args.force)
    except AptlyAPIException as e:
        if e.status_code in [404, 409]:
            raise AptlyCtlError(e) from e
        else:
            raise
    else:
        logger.info("Deleted repo %s" % args.name)
        return 0
