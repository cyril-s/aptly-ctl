from ..defaults import defaults

def config_subparser(subparsers_action_object):
    parser_put = subparsers_action_object.add_parser("put",
            description="Put packages in local repos.",
            help="Put packages in local repos.")
    parser_put.set_defaults(func=put)
    parser_put.add_argument("release", help="Release codename. E.g. jessie, stretch, etc.")
    parser_put.add_argument("component", help="Component name: E.g. main, rs, billing etc.")
    parser_put.add_argument("dist", help="Distribution component: E.g. stable, unstable etc.")
    parser_put.add_argument("packages", metavar="package", nargs="+", help="Pakcage to upload.")
    parser_put.add_argument("-U", "--upload-timeout", metavar="<seconds>",
            default=defaults["files"]["upload_timeout"],
            help="Timeout for files upload (defaults to %s seconds)." % defaults["files"]["upload_timeout"])


def put(args):
    print("I'm putting!")
    print(args)
