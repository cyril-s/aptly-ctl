#!/usr/bin/env python3

import argparse
from lib.defaults import defaults
import lib.plugins

if __name__ == "__main__":
    # main parser
    parser = argparse.ArgumentParser(
            description="Aptly API client with convenient defaults and functions.")
    parser.add_argument("-u", "--url", default=defaults["global"]["url"],
            help="Aptly API endpoint url.")
    parser.add_argument("--pass-file", metavar="<path>",
            default=defaults["publish"]["passphraze_file"],
            help="Path to gpg passphraze file local to aptly server.")

    subparsers = parser.add_subparsers(dest="subcommand")

    # init subparsers
    for plugin in lib.plugins.__all__:
        eval("lib.plugins.%s.config_subparser(subparsers)" % plugin)

    args = parser.parse_args()
    # run subcommand
    if args.subcommand:
        print(args.subcommand)
        args.func(args)
    else:
        parser.print_help()


