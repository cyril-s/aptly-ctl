import logging
import os
import yaml
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import nested_set

logger = logging.getLogger(__name__)

# map number of '-v' args to log level
VERBOSITY = frozenset(["WARN", "INFO", "DEBUG"])

class Config:

    defaults = {
            "url": None,
            "signing": {
                "skip": False,
                "batch": True,
                "gpg_key": None,
                "keyring": None,
                "secret_keyring": None,
                "passphrase": None,
                "passphrase_file": None
                }
            }

    try_files = ["%s/.config/aplty-ctl.conf", "/etc/aptly-ctl.conf"]

    def __init__(self, cfg_path=None, profile=0, cfg_overrides=[]):
        file_cfg = self._load_config(cfg_path)
        if file_cfg is None:
            file_cfg = {}
            profile_cfg = {}
        else:
            profile_cfg = self._get_profile_cfg(file_cfg, profile)

        cmd_line_cfg = self._parse_cmd_line_overrides(cfg_overrides)

        self._config = {}
        for d in [self.defaults, profile_cfg, cmd_line_cfg]:
            self._config.update(d)

        self._check_config(self._config)


    def __getitem__(self, key):
        return self._conf[key]


    def _check_config(self, config):
        if not config["url"]:
            raise DidwwAptlyCtlError("Specify url of API to connect to.")
        if not config["signing"]["skip"] and not config["signing"]["gpg_key"]:
            raise DidwwAptlyCtlError("Specify signing.gpg_key. Do not rely on default key.")
        if config["signing"]["passphrase"] is not None \
            and config["signing"]["passphrase_file"] is not None:
            raise DidwwAptlyCtlError("Specify either signing.passphrase or signing.passphrase_file.")
        if  config["signing"]["passphrase"] is None \
            and config["signing"]["passphrase_file"] is None:
            raise DidwwAptlyCtlError("Specify either signing.passphrase or signing.passphrase_file.")


    def _load_config(self, path=None):
        try_files = self.try_files[:]
        try:
            try_files[0] % os.environ["HOME"]
        except KeyError:
            logger.debug("Can't get $HOME")
            try_files.pop(0)

        if path:
            try_files.insert(0, path)

        config = None
        for i, p in enumerate(try_files):
            try:
                with open(p, "r") as f:
                    config = yaml.load(f)
            except FileNotFoundError as e:
                logger.debug('Can\'t load config from "%s"' % p)
                if i == 0:
                    raise DidwwAptlyCtlError(e)
            except yaml.YAMLError as e:
                raise DidwwAptlyCtlError("Cannot parse config: ", e)
            else:
                break

        return config


    def _get_profile_cfg(self, cfg, profile):
        try:
            profile_list = [ cfg["profiles"][int(profile)] ]
        except KeyError as e:
            raise DidwwAptlyCtlError("Config file doesn't have %s key." % e)
        except IndexError:
            raise DidwwAptlyCtlError("There is no profile numbered %s" % profile)
        except ValueError:
            profile_list = [ prof for prof in cfg["profiles"] if prof.get("name", "").startswith(profile) ]

        if len(profile_list) == 0:
            raise DidwwAptlyCtlError('Cannot find configuration profle "%s"' % profile)
        elif len(profile_list) > 1:
            raise DidwwAptlyCtlError('Profile "{}" equivocally matches {}'.format(profile, profile_list))
        else:
            return profile_list[0]

    
    def _parse_cmd_line_overrides(self, cfg_overrides):
        result = dict()
        for expr in cfg_overrides:
            key, sep, val = expr.partition("=")
            if len(sep) == 0 or len(key) == 0:
                raise DidwwAptlyCtlError('Wrong configuration key: "%s"' % expr)
            nested_set(result, key.split("."), val)
        else:
            return result

