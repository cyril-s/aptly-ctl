import logging
from pprint import pprint
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_repo = subparsers_action_object.add_parser("repo",
            help="List, show, create, edit and delete local repos.",
            description="List, show, create, edit and delete local repos.")
    parser_repo.set_defaults(func=repo)

    action_group = parser_repo.add_mutually_exclusive_group(required=True)
    action_group.add_argument("-l", "--list", action="store_true",
            help="List local repos.")

    action_group.add_argument("-s", "--show", metavar="repo",
            help="Show info about a local repo.")

    action_group.add_argument("-c", "--create", metavar="repo",
            help="Create a local repo.")

    action_group.add_argument("-e", "--edit", metavar="repo",
            help="Edit a local repo.")

    action_group.add_argument("-d", "--delete", metavar="repo",
            help="Delete a local repo.")

    parser_repo.add_argument("--detail", action="store_true",
            help="Print additional details when showing and listing.")


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


def repo(config, args):
    aptly = ExtendedAptlyClient(config["url"])

    if args.list:
        repo_list = aptly.repos.list()
        repo_list.sort(key=lambda k: k.name)
        for r in repo_list:
            if args.detail:
                pprint_repo(r)
            else:
                print(r.name)
    elif args.show:
        try:
            show_result = aptly.repos.show(args.show)
        except AptlyAPIException as e:
            if e.status_code == 404 and "local repo with name" in e.args[0].lower():
                raise DidwwAptlyCtlError(e)
            else:
                raise
        if args.detail:
            search_result = aptly.repos.search_packages(args.show)
            pprint_repo(show_result, search_result)
        else:
            pprint_repo(show_result)
    else:
        raise DidwwAptlyCtlError(NotImplementedError("Command not yet implemented"))

    return 0
