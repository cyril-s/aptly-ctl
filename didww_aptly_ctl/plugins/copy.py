"""
Uses aptly-api-client (https://github.com/gopythongo/aptly-api-client)
"""

import logging
from re import match
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import publish_update
from didww_aptly_ctl.utils import AptlyKey

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_copy = subparsers_action_object.add_parser("copy",
            description="Copies/Moves packages between components of the same distribution.",
            help=       "Copies/Moves packages between components of the same distribution.")
    parser_copy.set_defaults(func=copy)
    parser_copy.add_argument("-s", "--source", required=True,
            help="Triplet pointing to source repo. E.g. --source jessie_billing_unstable")
    parser_copy.add_argument("-t", "--target", required=True,
            help="Triplet pointing to target repo. E.g. --target jessie_billing_stable")
    parser_copy.add_argument("refs", metavar="package_referece", nargs="+",
            help="Can be direct referece (e.g. 'aptly_0.9~dev+217+ge5d646c_i386') or key \
                    (e.g. 'Pi386 libboost-program-options-dev 1.49.0.1 918d2f433384e378').")
    parser_copy.add_argument("-m", "--move", action="store_true",
            help="Remove packages from source.")
    parser_copy.add_argument("-k", "--keep-going", action="store_true",
            help="Keep going even if failed to find some packages in source repo.")


def copy(args):
    s_release = args.source.split("_")[0]
    t_release = args.target.split("_")[0]
    if s_release != t_release:
        raise DidwwAptlyCtlError("You can't move from {} release to {}".format(s_release, t_release))
    aptly = Client(args.url)

    #search package refs in source repo and get their keys (or validate if key supplied)
    dir_refs_to_validate = []
    for r in args.refs:
        if AptlyKey.key_regexp.match(r):
            dir_ref = AptlyKey(r).getDirRef()
            logger.debug("Converting '{}' to '{}'".format(r, dir_ref))
            dir_refs_to_validate.append(dir_ref)
        elif AptlyKey.dir_ref_regexp.match(r):
            dir_refs_to_validate.append(r)
        else:
            raise DidwwAptlyCtlError("Incorrect package reference: %s" % r, logger=logger)

    keys = []
    for r in dir_refs_to_validate:
        try:
            search_result = aptly.repos.search_packages(args.source, r)
        except AptlyAPIException as e:
            if e.status_code == 404:
                raise DidwwAptlyCtlError("Failed to search for package by direct referece.", e, logger)
            else:
                raise
        else:
            if len(search_result) == 0:
                if args.keep_going:
                    logger.warn("Failed to find {} in repo {}".format(r, args.source))
                else:
                    raise DidwwAptlyCtlError("Failed to find {} package in repo {}".format(r, args.source), logger=logger)
            elif len(search_result) == 1:
                keys.append(search_result[0][0])
            else:
                logger.warn("Skipping {}. Search by direct reference returned many results: {}".format(dir_ref, keys))
                if not args.keep_going:
                    raise DidwwAptlyCtlError("Failed to find {} package in repo {}".format(r, args.source), logger=logger)

    if len(keys) == 0: 
        raise DidwwAptlyCtlError("Could not find any package ref in source repo.", logger=logger)

    # Copy packages
    logger.info("Copying packages below from {} to {}".format(args.source, args.target))
    for k in keys:
        logger.info("    " + k)

    #TODO handle case when some of pakcages connot be copied because of conflict
    try:
        add_result = aptly.repos.add_packages_by_key(args.target, *keys)
    except AptlyAPIException as e:
        if e.status_code in [404, 400]:
            raise DidwwAptlyCtlError("Failed to copy packages.", e, logger)
        else:
            raise

    # Delete source if --move
    if args.move:
        delete_result = aptly.repos.delete_packages_by_key(args.source, *keys)

    # Update publishes
    update_result = publish_update(aptly, s_release, s_release, args.pass_file)
    logger.info("Updated publish {0}/{0}".format(s_release))
    logger.debug(update_result)

    return 0

