"""
Uses aptly-api-client (https://github.com/gopythongo/aptly-api-client)
"""

import logging
from re import match
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils import (
        aptly_key_regex,
        direct_reference_regex,
        aptly_key_to_direct_reference,
        direct_reference_to_aptly_key,
        publish_update,
        )

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_copy = subparsers_action_object.add_parser("copy",
            description="Copies/Moves packages between components of the same distribution.",
            help=       "Copies/Moves packages between components of the same distribution.")
    parser_copy.set_defaults(func=copy)
    parser_copy.add_argument("-s", "--source", nargs=3, required=True,
            help="Triplet pointing to source repo. E.g. --source jessie billing unstable")
    parser_copy.add_argument("-t", "--target", nargs=3, required=True,
            help="Triplet pointing to target repo. E.g. --target jessie billing stable")
    parser_copy.add_argument("refs", metavar="package_referece", nargs="+",
            help="Can be direct referece (e.g. 'aptly_0.9~dev+217+ge5d646c_i386') or key \
                    (e.g. 'Pi386 libboost-program-options-dev 1.49.0.1 918d2f433384e378').")
    parser_copy.add_argument("-m", "--move", action="store_true",
            help="Remove packages from source.")
    parser_copy.add_argument("-k", "--keep-going", action="store_true",
            help="Keep going even if failed to find some packages in source repo.")


def copy(args):
    if args.source[0] != args.target[0]:
        raise DidwwAptlyCtlError("You can't move from {} distribution to {}".format(args.source[0], args.target[0]))
    s_repo = "_".join([args.source[0], args.source[1], args.source[2]])
    t_repo = "_".join([args.target[0], args.target[1], args.target[2]])
    aptly = Client(args.url)

    #search package refs in source repo and get their keys (or validate if key supplied)
    dir_refs_to_validate = []
    for r in args.refs:
        if match(aptly_key_regex, r):
            dir_ref = aptly_key_to_direct_reference(r)
            logger.debug("Converting {} to {}".format(r, dir_ref))
            dir_refs_to_validate.append(dir_ref)
        elif match(direct_reference_regex, r):
            dir_refs_to_validate.append(r)
        else:
            raise DidwwAptlyCtlException("Incorrect package reference: %s" % r, logger=logger)

    keys = []
    for r in dir_refs_to_validate:
        search_result = aptly.repos.search_packages(s_repo, r)
        if len(search_result) == 0:
            if args.keep_going:
                logger.warn("Failed to find {} in repo {}".format(r, s_repo))
            else:
                raise DidwwAptlyCtlError("Failed to find {} package in repo {}".format(r, s_repo), logger=logger)
        elif len(search_result) == 1:
            keys.append(search_result[0]["key"])
        else:
            logger.warn("Skipping {}. Search by direct reference returned many results: {}".format(dir_ref, keys))
            if not args.keep_going:
                raise DidwwAptlyCtlError("Failed to find {} package in repo {}".format(r, s_repo), logger=logger)

    if len(keys) == 0: 
        raise DidwwAptlyCtlError("Could not find any package ref in source repo.", logger=logger)

    # Copy packages
    add_result = aptly.repos.add_packages_by_key(t_repo, keys)

    # Delete source if --move
    if args.move:
        delete_result = aptly.repos.delete_packages_by_key(s_repo, keys)

    # Update publishes
    update_result = publish_update(aptly, args.source[0], args.source[0])
    logger.info("Updated publish {}/{}".format(args.source[0]))
    logger.debug(update_result)

    return 0


