from ..defaults import defaults

def config_subparser(subparsers_action_object):
    parser_search = subparsers_action_object.add_parser("search",
            description="Search package in local repos.", help="Search package in local repos.")
    parser_search.set_defaults(func=search)
    parser_search.add_argument("name", help="Either regexp or path to deb package to search for.")


def search(args):
    print("I'm searching!")
    print(args)
