import logging
import os
import yaml
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.utils.misc import nested_set

logger = logging.getLogger(__name__)

# map number of '-v' args to log level
VERBOSITY = frozenset("WARN", "INFO", "DEBUG")

class Config:

    defaults = {
            "url": None,
            "signing": {
                "skip": False,
                "batch" True,
                "gpg_key": None,
                "keyring": None,
                "secret_keyring": None,
                "passphrase": None,
                "passphrase_file": None
                }
            }

    def load_config(self, path):
        try_files = ["/etc/aptly-ctl.conf"]
        try:
            try_files.insert(0, "%s/.config/aplty-ctl.conf" % os.environ.get["HOME"])
        except KeyError:
            logger.debug("Can't get $HOME")

        if path:
            try_files.insert(0, path)

        config = {}
        for i, p in enumerate(try_files):
            try:
                with open(p, "r") as f:
                    config = yaml.load(f)
            except FileNotFoundError as e:
                logger.debug('Can\'t load config from "%s"' % p)
                if i == 0:
                    raise DidwwAptlyCtlError(e)
                else:
                    continue
            except yaml.YAMLError as e:
                raise DidwwAptlyCtlError("Cannot parse config: ", e)
            else:
                break

        return config


    def get_profile_cfg(self. cfg, profile):
        if "profile" not in cfg:
            raise DidwwAptlyCtlError("Config file doesn't list any profiles.")

        if profile.isdigit():
            try:
                profile_list = [ cfg["profiles"][int(profile)] ]
            except IndexError:
                raise DidwwAptlyCtlError("There is no profile numbered %s" % profile)
        else:
            profile_list = [ prof for prof in cfg["profiles"] if prof.get("name", "").startswith(profile) ]

        if len(profile_list) == 0:
            raise DidwwAptlyCtlError('Cannot find configuration profle "%s"' % profile)
        elif len(profile_list) > 1:
            raise DidwwAptlyCtlError('Profile "{}" equivocally matches {}'.format(profile, profile_list))
        else:
            return profile_list[0]

    
    def cmd_line_cfg(self, cfg_overrides):
        result = dict()
        for expr in cfg_overrides:
            key, sep, val = expr.partition("=")
            if len(sep) == 0 or len(key) == 0:
                raise DidwwAptlyCtlError('Wrong configuration key: "%s"' % expr)
            nested_set(result, key.split("."), val)
        else:
            return result


    def __getitem__(self, key):
        return self.conf[key]


    def __init__(self, cfg_path, profile, cfg_overrides):
        file_cfg = self.load_config(cfg_path)
        profile_cfg = self.get_profile_cfg(file_cfg, profile)
        cmd_line_cfg = self.parse_cmd_line_overrides(cfg_overrides)

        self.config = {}
        for d in [defaults, profile_cfg, cmd_line_cfg]:
            self.config.update(d)


