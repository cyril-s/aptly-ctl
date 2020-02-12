import logging
from pprint import pprint
from aptly_ctl.utils.ExtendedAptlyClient import ExtendedAptlyClient
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils import PubSpec
from aptly_api.base import AptlyAPIException

logger = logging.getLogger(__name__)


def config_subparser(subparsers_action_object):
    parser_publish = subparsers_action_object.add_parser(
        "publish", help="administer publishes", description="Administer publishes"
    )
    subparsers = parser_publish.add_subparsers()

    parser_list = subparsers.add_parser(
        "list",
        help="list publishes",
        description="List publishes. STDOUT is a list of PUB_SPECs",
    )
    parser_list.set_defaults(func=list)
    parser_list.add_argument(
        "--detail",
        action="store_true",
        help="print additional details, makes STDOUT non-parsable",
    )

    parser_publish = subparsers.add_parser(
        "publish",
        aliases=["create"],
        help="publish snapshot/local repo",
        description="Publish snapshot/local repo. STDOUT is info on \
            newly created publish",
    )
    parser_publish.set_defaults(func=publish)
    parser_publish.add_argument(
        "name", metavar="PUB_SPEC", help="publish to create. See 'aptly-ctl --help'"
    )
    parser_publish.add_argument(
        "-s",
        "--source-kind",
        choices=["local", "snapshot"],
        required=True,
        help="publish from snapshots or local repos",
    )
    parser_publish.add_argument(
        "--architectures",
        default="",
        help="coma separated list of architectures to publish",
    )
    parser_publish.add_argument(
        "--label",
        default=None,
        help="value of 'Label:' field in published repository stanza",
    )
    parser_publish.add_argument(
        "--origin",
        default=None,
        help="value of 'Origin:' field in published repository stanza",
    )
    parser_publish.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite files in pool/ directory without notice",
    )
    #    parser_publish.add_argument("--not-automatic", action="store_true",.
    #            help="Indicates to the package manager to not install or upgrade packages from the repository without user consent").
    #    parser_publish.add_argument("--but-automatic-upgrades", action="store_true",.
    #            help="Excludes upgrades from the --not-automatic setting").
    #    parser_publish.add_argument("--stkip-cleanup", action="store_true",.
    #            help="Don’t remove unreferenced files in prefix/component").
    parser_publish.add_argument(
        "sources",
        metavar="source",
        nargs="+",
        help="""a local repo or snapshot to publish from of the form 'name=component'.
            Component can be omitted, then it is taken from default
            component of repo/snaphost, or set to 'main'
            """,
    )

    parser_update = subparsers.add_parser(
        "update",
        help="update published local repo or switch published snapshot",
        description="Update published local repo or switch published snapshot. \
                    STDOUT is info on updated publish",
    )
    parser_update.set_defaults(func=update)
    parser_update.add_argument(
        "name", metavar="PUB_SPEC", help="publish to update. See 'aptly-ctl --help'"
    )
    parser_update.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="overwrite files in pool/ directory without notice",
    )

    parser_drop = subparsers.add_parser(
        "drop",
        help="drop published repository",
        description="Drop published repository",
    )
    parser_drop.set_defaults(func=drop)
    parser_drop.add_argument(
        "name", metavar="PUB_SPEC", help="publish to drop. See 'aptly --help'"
    )
    parser_drop.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="delete publishesitory even if it has snapshots",
    )


def pprint_publish(pub):
    print(PubSpec(pub.distribution, pub.prefix))
    print("    Source kind: " + pub.source_kind)
    print("    Prefix: " + pub.prefix)
    print("    Distribution: " + pub.distribution)
    print("    Storage: " + pub.storage)
    print("    Label: " + pub.label)
    print("    Origin: " + pub.origin)
    print("    Architectures: " + ", ".join(pub.architectures))
    print("    Sources:")
    for s in pub.sources:
        print(" " * 8 + "{} ({})".format(s["Name"], s["Component"]))


def list(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    publish_list = aptly.publish.list()
    logger.debug("API returned: {}".format(publish_list))
    publish_list.sort(key=lambda p: repr(PubSpec(p.distribution, p.prefix)))
    for p in publish_list:
        if args.detail:
            pprint_publish(p)
        else:
            print(PubSpec(p.distribution, p.prefix))
    return 0


def update(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    try:
        p = PubSpec(args.name)
    except ValueError as e:
        raise AptlyCtlError(
            "PUB_SPEC '%s' invalid. See 'aptly-ctl --help'" % args.name
        ) from e
    s_cfg = config.get_signing_config(p).as_dict(prefix="sign_")
    try:
        result = aptly.publish.update(
            prefix=p.prefix,
            distribution=p.distribution,
            force_overwrite=args.force,
            **s_cfg
        )
    except AptlyAPIException as e:
        if e.status_code == 404:
            raise AptlyCtlError(e) from e
        else:
            raise
    logger.debug("Api returned: " + str(result))
    pprint_publish(result)
    return 0


def publish(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    try:
        p = PubSpec(args.name)
    except ValueError as e:
        raise AptlyCtlError(
            "PUB_SPEC '%s' invalid. See 'aptly-ctl --help'" % args.name
        ) from e
    s_cfg = config.get_signing_config(p).as_dict(prefix="sign_")
    architectures = args.architectures.split(",")
    sources = []
    for s in args.sources:
        name, sep, comp = s.partition("=")
        if len(name) == 0:
            raise AptlyCtlError
        elif len(comp) == 0:
            sources.append({"Name": name})
        else:
            sources.append({"Name": name, "Component": comp})
    try:
        result = aptly.publish.publish(
            prefix=p.prefix,
            distribution=p.distribution,
            source_kind=args.source_kind,
            sources=sources,
            architectures=architectures,
            label=args.label,
            origin=args.origin,
            force_overwrite=args.force,
            **s_cfg
        )
    except AptlyAPIException as e:
        raise AptlyCtlError(e) from e
    pprint_publish(result)
    return 0


def drop(config, args):
    aptly = ExtendedAptlyClient(config.url, timeout=args.timeout)
    try:
        p = PubSpec(args.name)
    except ValueError as e:
        raise AptlyCtlError(
            "PUB_SPEC '%s' invalid. See 'aptly-ctl --help'" % args.name
        ) from e
    s_cfg = config.get_signing_config(p).as_dict(prefix="sign_")
    try:
        aptly.publish.drop(
            prefix=p.prefix, distribution=p.distribution, force_delete=args.force
        )
    except AptlyAPIException as e:
        raise AptlyCtlError(e) from e
    return 0
