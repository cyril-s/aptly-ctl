"""
usage: didww-aptly-cli.py put [-h] [-U <seconds>] release component dist package [package ...]

Does 3 things:
    * Upload packages to aptly server;
    * Adds packages to specified repo;
    * Updates correspoding publish.
Uses aptly-api-client (https://github.com/gopythongo/aptly-api-client)
"""

from datetime import datetime
from aptly_api import Client
from requests import put as requests_put, HTTPError, ConnectionError
from aptly_api.base import AptlyAPIException

def config_subparser(subparsers_action_object):
    parser_put = subparsers_action_object.add_parser("put",
            description="Put packages in local repos.",
            help="Put packages in local repos.")
    parser_put.set_defaults(func=put)
    parser_put.add_argument("release", help="Release codename. E.g. jessie, stretch, etc.")
    parser_put.add_argument("component", help="Component name: E.g. main, rs, billing etc.")
    parser_put.add_argument("dist", help="Distribution component: E.g. stable, unstable etc.")
    parser_put.add_argument("packages", metavar="package", nargs="+", help="Pakcage to upload.")


def _custom_publish_update(args):
    full_url = "{0}/publish/{1}/{1}".format(args.url, args.release)
    data = {
            "Signing": {
                "PassphraseFile": args.pass_file
                }
            }
    #data["Signing"]["GpgKey"] = "/home/pkg/didww.pgp" # to get 500 uncomment this
    try:
        r = requests_put(full_url, json=data)
        r.raise_for_status()
    except HTTPError as e:
        raise AptlyAPIException(e, status_code=e.response.status_code)
    #TODO return PublishEndpoint
    return (r.status_code, r.request.url)


def put(args):
    repo = "_".join([args.release, args.component, args.dist])
    timestamp = datetime.utcnow().timestamp()
    directory = repo + "_" + str(int(timestamp))
    aptly = Client(args.url)

    # Upload packages
    print("INFO: Uploading packages\n  {}\nto repo {} on {}".format("\n  ".join(args.packages), repo, args.url))
    try:
        upload_result = aptly.files.upload(directory, *args.packages)
    except ConnectionError as e:
        print("ERR:", e)
        #TODO better throw exception
        return
        
    # Add them to repo
    print("INFO: Adding packages to repo.")
    if len(upload_result) != 0:
        add_result = aptly.repos.add_uploaded_file(repo, directory)
        for failed in add_result.failed_files:
            print("WARN: Failed to add %s to %s" % (failed, repo))
        for warning in add_result.report["Warnings"]:
            print("WARN: %s" % warning)
        for added in add_result.report["Added"]:
            print("INFO: Added %s to %s" % (added, repo))
        for removed in add_result.report["Removed"]:
            print("INFO: Removed %s to %s" % (removed, repo))
    else:
        print("ERR: Failed to upload any package.")
        return

    # Update publish
    if len(add_result.report["Added"]) + len(add_result.report["Removed"]) != 0:
        try:
            update_result = aptly.publish.update(prefix=args.release,
                    distribution=args.release, sign_passphrase_file=args.pass_file)
            print(update_result)
        except AptlyAPIException as e:
            if e.args[0] == "Update needs a gpgkey to sign with if sign_skip is False":
                # aptly_api 0.1.5 throws exception when sign_gpgkey is not passed.
                # But it is ok because aplty polls gpg agent for key from keyring.
                # So we update publish here manually.
                (update_result, update_url) = _custom_publish_update(args)
                if update_result == 200:
                    print("INFO: Updated publish at %s" % update_url)
            else:
                raise e
    else:
        print("WARN: Nothing added or removed. Skipping publish update.")
        return


