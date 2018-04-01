import logging
import os
import yaml
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError

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

        config = None
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
                

    def __init__(self, profile, cfg_overrides, cfg_path):
        config = default.copy()
        cfg = self.load_config(cfg_path)
        if cfg is not None:
            config = self.get_profile_cfg(cfg, profile)

