import logging
from datetime import datetime
from aptly_api.base import AptlyAPIException
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils import PackageRef, PackageFile

logger = logging.getLogger(__name__)


def config_subparser(subparsers_action_object):
    parser_put = subparsers_action_object.add_parser(
        "put",
        help="put packages in local repos",
        description="""
            Put packages in local repos and update dependent publishes.
            STDOUT is a list of newly uploaded package_references
            """,
    )

    parser_put.set_defaults(func=put)
    parser_put.add_argument("repo", help="destination repository name")

    parser_put.add_argument(
        "packages",
        metavar="package",
        nargs="*",
        help="pakcages to upload. If omitted, file paths are read from STDIN",
    )

    parser_put.add_argument(
        "-f",
        "--force-replace",
        action="store_true",
        help="remove packages conflicting with package being added",
    )


def put(config, args):
    timestamp = datetime.utcnow().timestamp()
    directory = "{}_{:.0f}".format(args.repo, timestamp)
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)

    # don't try to upload files if repos does not exist
    try:
        aptly.repos.show(args.repo)
    except AptlyAPIException as e:
        if e.status_code == 404:
            raise AptlyCtlError("Local repo '%s' not found." % args.repo) from e
        else:
            raise

    packages = []
    for p in args.packages:
        try:
            packages.append(PackageFile(p))
        except OSError as e:
            raise AptlyCtlError("Failed to load package: {}".format(e))

    logger.info('Uploading the packages to directory "%s"' % directory)
    try:
        upload_result = aptly.files.upload(directory, *args.packages)
    except AptlyAPIException as e:
        if e.status_code == 0 and e.args[0].startswith("File to upload"):
            raise AptlyCtlError(e) from e
        else:
            raise
    else:
        logger.debug("Upload result: %s" % ",".join(upload_result))

    try:
        add_result = aptly.repos.add_uploaded_file(
            args.repo, directory, force_replace=args.force_replace
        )
    finally:
        logger.info("Deleting directory '%s'." % directory)
        aptly.files.delete(path=directory)

    logger.debug("Package add failed files: %s" % add_result.failed_files)
    for f in add_result.failed_files:
        logger.warning('"Failed to add package "%s"' % f)
    logger.debug("Package add warnings: %s" % add_result.report["Warnings"])
    for f in add_result.report["Warnings"]:
        logger.warning(f)
    logger.debug("Package add 'Removed' section: %s" % add_result.report["Removed"])
    for f in add_result.report["Removed"]:
        logger.info('Removed "%s"' % f)
    logger.debug("Package add 'Added' section: %s" % add_result.report["Added"])
    for f in add_result.report["Added"]:
        # renamed deb packages won't be displayed
        dir_ref = f.split()[0]
        filename = dir_ref + ".deb"
        orig_file = [p for p in packages if p.filename == filename]
        if len(orig_file) == 0:
            # probably original deb file was renamed
            logger.warning(
                'For added package "{}" there were no match in original deb files'.format(
                    dir_ref
                )
            )
        else:
            if len(orig_file) > 1:
                logger.warning(
                    'For added package "{}" there were more than one match in original deb files: {}'.format(
                        dir_ref, orig_file
                    )
                )
            added_ref = PackageRef(args.repo + "/" + dir_ref)
            added_ref.hash = format(orig_file[0].ahash, "x")
            print('"{!r}"'.format(added_ref))

    if len(add_result.report["Added"]) + len(add_result.report["Removed"]) == 0:
        logger.warning("Skipping publish update.")
        raise AptlyCtlError("Nothing added or removed.")

    update_exceptions = aptly.update_dependent_publishes([args.repo], config)
    if len(update_exceptions) > 0:
        raise AptlyCtlError("Some publishes fail to update.")
    else:
        return 0
