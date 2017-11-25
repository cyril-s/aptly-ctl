from ..defaults import defaults

def config_subparser(subparsers_action_object):
    descr_msg = """
    Simple interface to query aply local repos for packages.
    It searches by control file fields (namely Name, Version, Architecture)
    Name and Architecture are searched by wildcard ([^]?* symbols).
    Version filed is searched  by operators >=, <=, =, >>, << according to apt rules.
    Operator must precede version (e.g. ">=1.0.1" or ">= 1.0.1"). If not, default is '='.
    Fields search expressions ANDed together.
    It returns list of keys of found packages.
    """
    parser_search = subparsers_action_object.add_parser("search",
            description=descr_msg, help="Search package in local repos.")
    parser_search.set_defaults(func=search)
    parser_search.add_argument("-n", "--name", help="Name of package to search for.")
    parser_search.add_argument("-v", "--version", help="Version of package to search for.")
    parser_search.add_argument("-a", "--arch", help="Architecture of package to search for.")


def search_package_in_repo(client, repo, name="*", version=None, architecture=None):
    raise NotImplementedError


def search_package(client, name="*", version=None, architecture=None):
    raise NotImplementedError


def search(args):
    print("I'm searching!")
    print(args)


