import logging
from pprint import pprint
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_repo = subparsers_action_object.add_parser("repo",
            help="Administer local repos",
            description="Administer local repos")
    subparsers = parser_repo.add_subparsers()

    parser_list = subparsers.add_parser("list", help="List local repos")
    parser_list.set_defaults(func=list)
    parser_list.add_argument("--detail", action="store_true",
            help="Print additional details when showing and listing")

    parser_create = subparsers.add_parser("create", help="Create a local rep")
    parser_create.set_defaults(func=create)
    parser_create.add_argument("name", help="Name of new repo")
    parser_create.add_argument("--comment", help="Text describing local repository for a user")
    parser_create.add_argument("--dist", help="Default distribution when publishing from this local repo")
    parser_create.add_argument("--comp", help="Default component when publishing from this local repo")

    parser_edit = subparsers.add_parser("edit", help="Edit a local repo")
    parser_edit.set_defaults(func=edit)
    parser_edit.add_argument("name", help="Name of a repo")
    parser_edit.add_argument("--comment", help="Text describing local repository for a user")
    parser_edit.add_argument("--dist", help="Default distribution when publishing from this local repo")
    parser_edit.add_argument("--comp", help="Default component when publishing from this local repo")

    parser_delete = subparsers.add_parser("delete", help="Delete a local repo")
    parser_delete.set_defaults(func=delete)
    parser_delete.add_argument("name", help="Name of a repo")
    parser_delete.add_argument("-f", "--force", action="store_true",
            help="Delete local repository even if it has snapshots")


def pprint_repo(repo, packages=[]):
    print(repo.name)
    print("    Default distribution: " + repo.default_distribution)
    print("    Default component: " + repo.default_component)
    print("    Comment: " + repo.comment)
    if packages:
        print("    Packages:")
        packages.sort(key=lambda p: PackageRef(p.key))
        for p in packages:
            print(" "*8 + '"%s"' % p.key)


def list(config, args):
    aptly = ExtendedAptlyClient(config.url)
    repo_list = aptly.repos.list()
    repo_list.sort(key=lambda k: k.name)
    for r in repo_list:
        if args.detail:
            pprint_repo(r)
        else:
            print(r.name)
    return 0


def create(config, args):
    aptly = ExtendedAptlyClient(config.url)
    try:
        create_result = aptly.repos.create(args.name, args.comment, args.dist, args.comp)
    except AptlyAPIException as e:
        if e.status_code == 400:
            raise DidwwAptlyCtlError(e)
        else:
            raise
    else:
        logger.info("Created repo {}".format(create_result))
        return 0


def edit(config, args):
    aptly = ExtendedAptlyClient(config.url)
    try:
        edit_result = aptly.repos.edit(args.name, args.comment, args.dist, args.comp)
    except AptlyAPIException as e:
        if e.status_code in [0, 404]:
            raise DidwwAptlyCtlError(e)
        else:
            raise
    else:
        logger.info("Edited repo: {}".format(edit_result))
        return 0


def delete(config, args):
    aptly = ExtendedAptlyClient(config.url)
    try:
        aptly.repos.delete(args.name, args.force)
    except AptlyAPIException as e:
        if e.status_code in [404, 409]:
            raise DidwwAptlyCtlError(e)
        else:
            raise
    else:
        logger.info("Deleted repo %s" % args.name)
        return 0
