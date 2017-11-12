#!/usr/bin/env python3

import argparse
from didww-aptly-cli-lib.defaults import defaults
import didww-aptly-cli-lib.funcs

if __name__ == "__name__":
    # main parser
    parser = argparse.ArgumentParser(
            description="Aptly API client with convenient defaults and functions.")
    parser.add_argument("-u", "--url", default=defaults["global"]["url"],
            help="Aptly API endpoint url.")
    parser.add_argument("--pass-file", metavar="<path>",
            default=defaults["publish"]["passphraze_file"],
            help="Path to gpg passphraze file local to aptly server.")

    subparsers = parser.add_subparsers()

    # put parser
    parser_put = subparsers.add_parser("put", help="Put packages in local repos.")
    parser_put.set_defaults(func=didww-aptly-cli-lib.funcs.put)
    parser_put.add_argument("release", help="Release codename. E.g. jessie, stretch, etc.")
    parser_put.add_argument("component", help="Component name: E.g. main, rs, billing etc.")
    parser_put.add_argument("dist", help="Distribution component: E.g. stable, unstable etc.")
    parser_put.add_argument("packages", metavar="package", nargs="+", help="Pakcage to upload.")
    parser_put.add_argument("-U", "--upload-timeout", metavar="<seconds>",
            default=defaults["files"]["upload_timeout"],
            help="Timeout for files upload (defaults to %s seconds)." % defaults["files"]["upload_timeout"])

    # search parser
    parser_search = subparsers.add_parser("search", help="Search package in local repos.")
    parser_search.set_defaults(func=didww-aptly-cli-lib.funcs.search)
    parser_put.add_argument("name", help="Either regexp or path to deb package to search for.")

    args = parser.parse_args()
    # run subcommand
    args.func(args)


