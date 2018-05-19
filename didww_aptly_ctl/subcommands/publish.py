import logging
from pprint import pprint
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from aptly_api.base import AptlyAPIException

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_publish = subparsers_action_object.add_parser("publish",
            help="List, publish, update and drop publishes.",
            description="List, publish, update and drop publishes.")
    parser_publish.set_defaults(func=publish)

    action_group = parser_publish.add_mutually_exclusive_group(required=True)
    action_group.add_argument("-l", "--list", action="store_true",
            help="List publishes.")

    action_group.add_argument("-p", "--publish", metavar="publish",
            help="Publish snapshot or local repo.")

    action_group.add_argument("-u", "--update", metavar="publish",
            help="Update published local repo or switch published snapshot.")

    action_group.add_argument("-d", "--drop", metavar="publish",
            help="Drop published repository.")


def publish(config, args):
    aptly = ExtendedAptlyClient(config["url"])

    if args.list:
        publish_list = aptly.publish.list()
        publish_list.sort(key=lambda k: k.prefix + k.distribution)
        for p in publish_list:
            pprint(p)
    else:
        raise DidwwAptlyCtlError(NotImplementedError("Command not yet implemented"))

    return 0
