"""
usage: didww-aptly-cli.py put [-h] [-U <seconds>] release component dist package [package ...]

Does 3 things:
    * Upload packages to aptly server;
    * Adds packages to specified repo;
    * Updates correspoding publish.
Uses aptly-api-client (https://github.com/gopythongo/aptly-api-client)
"""

import logging
from datetime import datetime
from aptly_api import Client
from requests import put as requests_put, HTTPError, ConnectionError
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.exceptions import DidwwAptlyCtlException

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
    logger.info("Trying to remove upload directory %s" % directory)
    client.files.delete(path=directory)
    logger.info("Managed to remove upload directory %s" % directory)


def _custom_publish_update(args):
    full_url = "{0}/publish/{1}/{1}".format(args.url, args.release)
    data = dict()
    data["Signing"] = dict()
    data["Signing"]["PassphraseFile"] = args.pass_file
    #data["Signing"]["GpgKey"] = "/home/pkg/didww.pgp" # to get 500 uncomment this
    try:
        r = requests_put(full_url, json=data)
        r.raise_for_status()
    except HTTPError as e:
        raise DidwwAptlyCtlException(e, logger=logger)
    #TODO return PublishEndpoint
    return (r.status_code, r.request.url)


def put(args):
    repo = "_".join([args.release, args.component, args.dist])
    timestamp = datetime.utcnow().timestamp()
    directory = repo + "_" + str(int(timestamp))
    aptly = Client(args.url)

    # Upload packages
    logger.info("Uploading the packages below to repo {} on {}".format(repo, args.url))
    for p in args.packages:
        logger.info("    " + p)
    try:
        upload_result = aptly.files.upload(directory, *args.packages)
    except ConnectionError as e:
        raise DidwwAptlyCtlException(e, logger=logger)

    if len(upload_result) == 0:
        raise DidwwAptlyCtlException("Failed to upload any package.", logger=logger)
        
    # Add them to repo
    logger.info("Adding packages to repo.")
    try:
        add_result = aptly.repos.add_uploaded_file(repo, directory)
    except AptlyAPIException as e:
        logger.error("Failed to add files to repo. API returned %s" % e.status_code)
        try:
            _remove_upload_dir(aptly, directory)
        except Exception as e2:
            logger.error("Failed to remove upload directory %s" % directory)
            raise DidwwAptlyCtlException(e2, logger=logger)
        raise DidwwAptlyCtlException(e, logger=logger)
    except ConnectionError as e:
        raise DidwwAptlyCtlException(e, logger=logger)

    for failed in add_result.failed_files:
        logger.warn("Failed to add %s to %s" % (failed, repo))
    for warning in add_result.report["Warnings"]:
        logger.warn(warning)
    for added in add_result.report["Added"]:
        logger.info("%s to %s" % (added, repo))
    for removed in add_result.report["Removed"]:
        logger.info("Removed %s to %s" % (removed, repo))

    if len(add_result.failed_files) != 0:
        _remove_upload_dir(aptly, directory)

    # Update publish
    if len(add_result.report["Added"]) + len(add_result.report["Removed"]) == 0:
        logger.warn("Skipping publish update.")
        raise DidwwAptlyCtlException("Nothing added or removed.", logger=logger)
    else:
        try:
            update_result = aptly.publish.update(prefix=args.release,
                    distribution=args.release, sign_passphrase_file=args.pass_file)
            logger.info("Updated publish.")
        except AptlyAPIException as e:
            if e.args[0] == "Update needs a gpgkey to sign with if sign_skip is False":
                # aptly_api 0.1.5 throws exception when sign_gpgkey is not passed.
                # But it is ok because aplty polls gpg agent for key from keyring.
                # So we update publish here manually.
                (update_result, update_url) = _custom_publish_update(args)
                if update_result == 200:
                    logger.info("Updated publish at %s" % update_url)
            else:
                raise DidwwAptlyCtlException(e, logger=logger)

    return 0


