import logging
import os
import yaml
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import nested_set, nested_update

logger = logging.getLogger(__name__)

# map number of '-v' args to log level
VERBOSITY = ("WARN", "INFO", "DEBUG")

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

    try_files_home = [
        "{home}/aptly-ctl.yml",
        "{home}/aptly-ctl.yaml",
        "{home}/aptly-ctl.conf",
        "{home}/.aptly-ctl.yml",
        "{home}/.aptly-ctl.yaml",
        "{home}/.aptly-ctl.conf",
        "{home}/.config/aptly-ctl.yml",
        "{home}/.config/aptly-ctl.yaml",
        "{home}/.config/aptly-ctl.conf",
        ]

    try_files_system = [
        "/etc/aptly-ctl.conf",
        ]

    def __init__(self, cfg_path=None, profile=0, cfg_overrides=[]):
        if cfg_path is None:
            if "HOME" in os.environ:
                for i in range(len(self.try_files_home)):
                    self.try_files_home[i] = self.try_files_home[i].format(home=os.environ["HOME"])
            else:
                logger.warn("Could not get $HOME.")
                self.try_files_home = []
            try_files = self.try_files_home + self.try_files_system
        else:
            try_files = [cfg_path]

        try:
            file_cfg = self._load_config(try_files)
        except DidwwAptlyCtlError as e:
            logger.warn("Could not get config from these files: " + ", ".join(try_files))
            file_cfg = {}
            profile_cfg = {}
        else:
            profile_cfg = self._get_profile_cfg(file_cfg, profile)

        cmd_line_cfg = self._parse_cmd_line_overrides(cfg_overrides)

        self._config = {}
        for d in [self.defaults, profile_cfg, cmd_line_cfg]:
            nested_update(self._config, d)

        logger.debug("Config before check: %s" % self._config)
        self._check_config()


    def __getitem__(self, key):
        return self._config[key]


    def _check_config(self):
        if not self["url"]:
            raise DidwwAptlyCtlError("Specify url of API to connect to.")
        if not self["signing"]["skip"] and not self["signing"]["gpg_key"]:
            raise DidwwAptlyCtlError("Specify signing.gpg_key. Do not rely on default key.")
        if self["signing"]["passphrase"] is not None \
            and self["signing"]["passphrase_file"] is not None:
            raise DidwwAptlyCtlError("Specify either signing.passphrase or signing.passphrase_file.")
        if  self["signing"]["passphrase"] is None \
            and self["signing"]["passphrase_file"] is None:
            raise DidwwAptlyCtlError("Specify either signing.passphrase or signing.passphrase_file.")


    def _load_config(self, files):
        "Try to load config from the first existing file and throw DidwwAptlyCtlError if options are exausted"
        for file in files:
            try:
                with open(file, "r") as f:
                    c = yaml.load(f)
                    logger.info('Loadded config from "%s"' % file)
                    return c
            except FileNotFoundError as e:
                logger.debug('Can\'t load config from "%s"' % file)
            except yaml.YAMLError as e:
                raise DidwwAptlyCtlError("Cannot parse config: ", e)
        else:
            raise DidwwAptlyCtlError("Could not find config file.")


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

