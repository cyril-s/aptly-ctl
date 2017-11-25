# Install
Add apt source:
```bash
echo "deb http://pkg.in.didww.com/debian/stretch stretch misc-stable" \
    | sudo tee /etc/apt/sources.list.d/didww-misc.list
```
Fetch key:
```bash
wget -O - http://pkg.in.didww.com/key.gpg | sudo apt-key add -
```
Optionally configure apt pinning:
```bash
cat > >(sudo tee /etc/apt/preferences.d/didww-pref) <<EOF
Package: *
Pin: origin "pkg.in.didww.com"
Pin-Priority: 150

Package: didww-aptly-ctl
Pin: origin "pkg.in.didww.com"
Pin-Priority: 500
EOF
```
Install:
```bash
apt-get install didww-aptly-ctl
```
# Use
To see full traceback of handled exceptions  supply `-L debug`
# Develop
Functionality is extended by creating modules in `didww_aptly_ctl/plugins/` directory.
Do:
* Define method `config_subparser(subparser)` where you can configure subcommand of `argparse` module
* Use module level `logger = logging.getLogger(__name__)`
* Log event using `logger`. Messages go to stderr. Use `print()` if your plugin has output
* Use `didww_aptly_ctl.exceptions.DidwwAptlyCtlError` exception

Here is blueprint to start:
```python
import logging

logger = logging.getLogger(__name__)

def config_subparser(subparsers_action_object):
    parser_remove = subparsers_action_object.add_parser("remove",
        description="Removes packages from local repos.",
        help=       "Removes packages from local repos.")
    # entry point function
    parser_copy.set_defaults(func=remove)
    parser_copy.add_argument("-r", "--repo", help="Repo name from where to remove packages.")


def remove(args):
    logger.info("My args: %s" % args)
    return 0
```
