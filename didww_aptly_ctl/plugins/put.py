"""
usage: didww-aptly-cli.py put [-h] [-U <seconds>] release component dist package [package ...]

Uses aptly-api-client (https://github.com/gopythongo/aptly-api-client)
Does 3 things:
    * Upload packages to aptly server;
    * Adds packages to specified repo;
    * Updates correspoding publish.

STDOUT: List of direct references of added packages
"""

import logging
from datetime import datetime
from aptly_api import Client
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import publish_update

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_put = subparsers_action_object.add_parser("put",
            description="Put packages in local repos.",
            help="Put packages in local repos.")
    parser_put.set_defaults(func=put)
    parser_put.add_argument("release", help="Release codename. E.g. jessie, stretch, etc.")
    parser_put.add_argument("component", help="Component name: E.g. main, rs, billing etc.")
    parser_put.add_argument("dist", help="Distribution component: E.g. stable, unstable etc.")
    parser_put.add_argument("packages", metavar="package", nargs="+", help="Pakcage to upload.")


def _remove_upload_dir(client, directory):
    try:
        client.files.delete(path=directory)
    except Exception as e:
        logger.error("Failed to remove upload directory %s" % directory)
        raise
    else:
        logger.info("Remove upload directory %s" % directory)


def put(args):
    repo = "_".join([args.release, args.component, args.dist])
    timestamp = datetime.utcnow().timestamp()
    directory = repo + "_" + str(int(timestamp))
    aptly = Client(args.url)

    # Upload packages
    logger.info("Uploading the packages below to repo {} on {}".format(repo, args.url))
    for p in args.packages:
        logger.info("    " + p)
    upload_result = aptly.files.upload(directory, *args.packages)

    if len(upload_result) == 0:
        raise DidwwAptlyCtlError("Failed to upload any package.")
        
    # Add them to repo
    logger.info("Adding packages to repo.")
    add_result = None
    try:
        add_result = aptly.repos.add_uploaded_file(repo, directory)
    except AptlyAPIException as e:
        raise DidwwAptlyCtlError(
                "Failed to add files to repo. API returned %s" % e.status_code,
                original_exception=e,
                logger=logger)
    finally:
        if add_result is None or len(add_result.failed_files) != 0:
            _remove_upload_dir(aptly, directory)

    for failed in add_result.failed_files:
        logger.warn("Failed to add %s to %s" % (failed, repo))
    for warning in add_result.report["Warnings"]:
        logger.warn(warning)
    added_dir_refs = []
    for added in add_result.report["Added"]:
        logger.info("%s to %s" % (added, repo))
        added_dir_refs.append(added.split(" ")[0])
    for removed in add_result.report["Removed"]:
        logger.info("Removed %s to %s" % (removed, repo))

    if len(add_result.report["Added"]) + len(add_result.report["Removed"]) == 0:
        logger.warn("Skipping publish update.")
        raise DidwwAptlyCtlError("Nothing added or removed.")

    # Update publish
    update_result = publish_update(aptly, args.release, args.release, args.pass_file)
    logger.info("Updated publish {0}/{0}".format(args.release))
    logger.debug(update_result)
    print("\n".join(added_dir_refs))

    return 0


