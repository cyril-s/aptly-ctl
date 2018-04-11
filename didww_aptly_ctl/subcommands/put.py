import logging
from datetime import datetime
from aptly_api.base import AptlyAPIException
from didww_aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.PackageRef import PackageRef

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_put = subparsers_action_object.add_parser("put",
            description="Put packages in local repos and update dependent publishes.",
            help="Put packages in local repos and update dependent publishes.")

    parser_put.set_defaults(func=put)
    parser_put.add_argument("repo",
        help="Destination repository name.")

    parser_put.add_argument("packages", metavar="package", nargs="*",
        help="Pakcages to upload. If omitted, file paths are read from stdin.")

    parser_put.add_argument("-f", "--force-replace", action="store_true",
        help="Remove packages conflicting with package being added.")


def put(config, args):
    timestamp = datetime.utcnow().timestamp()
    directory = "{}_{:.0f}".format(args.repo, timestamp)
    aptly = ExtendedAptlyClient(config["url"])

    # don't try to upload files if repos does not exist
    try:
        aptly.repos.show(args.repo)
    except AptlyAPIException as e:
        if e.status_code == 404:
            raise DidwwAptlyCtlError(e)
        else:
            raise

    logger.info('Uploading the packages to directory "%s"' % directory)
    try:
        upload_result = aptly.files.upload(directory, *args.packages)
    except AptlyAPIException as e:
        if e.status_code == 0 and r.args[0].startswith("File to upload"):
            raise DidwwAptlyCtlError(e)
        else:
            raise
    else:
        logger.debug("Upload result: %s" % upload_result)

    try:
        add_result = aptly.repos.add_uploaded_file(args.repo, directory,
                force_replace=args.force_replace)
    finally:
        aptly.files.delete(path=directory)
    else:
        logger.debug("Package add result: %s" % add_result)
        for f in add_result.filed_files:
            logger.warn('"Failed to add package "%s"' % f)
        for f in add_result.report["Warnings"]:
            logger.warn(f)
        for f in add_result.report["Removed"]:
            logger.info('Removed "%s"' % f)
        for f in add_result.report["Added"]:
            print(repr(PackageRef(f, args.repo)))

    if len(add_result.report["Added"]) + len(add_result.report["Removed"]) == 0:
        logger.warn("Skipping publish update.")
        raise DidwwAptlyCtlError("Nothing added or removed.")

    pubs = aptly.lookup_publish_by_repos([args.repo])
    for p in pubs:
        update_result = aptly.publish.update(
                prefix = p.prefix,
                distribution = p.distribution,
                sign_skip = config["signing"]["skip"],
                sign_batch = config["signing"]["batch"],
                sign_gpgkey = config["signing"]["gpg_key"],
                sign_keyring = config["signing"]["keyring"],
                sign_secret_keyring = config["signing"]["secret_keyringkeyring"],
                sign_passphrase = config["signing"]["passphrase"],
                sign_passphrase_file = config["signing"]["passphrase_file"],
                )
        logger.info("Updated publish {}/{}".format(p.prefix, p.distribution))
        logger.debug('Update result for "{}/{}: {}"'.format(
                p.prefix, p.distribution, update_result))
        
    return 0
