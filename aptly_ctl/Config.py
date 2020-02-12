import logging
import os
import yaml
import errno
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.utils.misc import nested_set, nested_update
from aptly_ctl.utils import PubSpec

logger = logging.getLogger(__name__)

# map number of '-v' args to log level
VERBOSITY = ("WARN", "INFO", "DEBUG")


class SigningConfig:
    def __init__(
        self,
        skip=False,
        batch=True,
        gpgkey=None,
        keyring=None,
        secret_keyring=None,
        passphrase=None,
        passphrase_file=None,
        **kwargs
    ):
        if kwargs:
            unknown_keys = []
            for k, v in kwargs.items():
                unknown_keys.append("{}={}".format(k, v))
            raise AptlyCtlError("Unknown configuration keys: {}".format(unknown_keys))

        if not skip:
            if not gpgkey:
                raise AptlyCtlError(
                    "Config must contain 'gpgkey'. Do not rely on default key."
                )
            if (passphrase and passphrase_file) or (
                not passphrase and not passphrase_file
            ):
                raise AptlyCtlError(
                    "Config must contain either 'passphrase' or 'passphrase_file'."
                )
        self._conf = {
            "skip": skip,
            "batch": batch,
            "gpgkey": gpgkey,
            "keyring": keyring,
            "secret_keyring": secret_keyring,
            "passphrase": passphrase,
            "passphrase_file": passphrase_file,
        }

    @property
    def skip(self):
        return self._conf["skip"]

    @property
    def batch(self):
        return self._conf["batch"]

    @property
    def gpgkey(self):
        return self._conf["gpgkey"]

    @property
    def keyring(self):
        return self._conf["keyring"]

    @property
    def secret_keyring(self):
        return self._conf["secret_keyring"]

    @property
    def passphrase(self):
        return self._conf["passphrase"]

    @property
    def passphrase_file(self):
        return self._conf["passphrase_file"]

    def as_dict(self, prefix=""):
        return {
            "{prefix}skip".format(prefix=prefix): self.skip,
            "{prefix}batch".format(prefix=prefix): self.batch,
            "{prefix}gpgkey".format(prefix=prefix): self.gpgkey,
            "{prefix}keyring".format(prefix=prefix): self.keyring,
            "{prefix}secret_keyring".format(prefix=prefix): self.secret_keyring,
            "{prefix}passphrase".format(prefix=prefix): self.passphrase,
            "{prefix}passphrase_file".format(prefix=prefix): self.passphrase_file,
        }


class Config:

    defaults = {}

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
        "/etc/aptly-ctl.yml",
        "/etc/aptly-ctl.yaml",
        "/etc/aptly-ctl.conf",
    ]

    def __init__(self, cfg_path=None, profile=0, cfg_overrides=[]):
        if cfg_path is None:
            if "HOME" in os.environ:
                for i in range(len(self.try_files_home)):
                    self.try_files_home[i] = self.try_files_home[i].format(
                        home=os.environ["HOME"]
                    )
            else:
                logger.warning("Could not get $HOME.")
                self.try_files_home = []
            try_files = self.try_files_home + self.try_files_system
        elif cfg_path is False:
            try_files = []
        else:
            try_files = [cfg_path]

        file_cfg = self._load_config(try_files, fail_fast=(cfg_path is not None))
        if file_cfg is None:
            profile_cfg = {}
        else:
            profile_cfg = self._get_profile_cfg(file_cfg, profile)

        cmd_line_cfg = self._parse_cfg_overrides(cfg_overrides)

        config = {}
        for d in [self.defaults, profile_cfg, cmd_line_cfg]:
            nested_update(config, d)

        self._default_signing_config = SigningConfig(**config["signing"])
        self._signing_overrides = {}
        if "signing_overrides" in config:
            for pub, cfg in config["signing_overrides"].items():
                self._signing_overrides[pub] = SigningConfig(**cfg)

        try:
            self.name = config["name"]
        except KeyError:
            pass

        try:
            self.url = config["url"]
        except KeyError as e:
            raise AptlyCtlError("Specify url of API to connect to.") from e

    def get_signing_config(self, pub_spec=None):
        if pub_spec is None:
            return self._default_signing_config
        elif not isinstance(pub_spec, PubSpec):
            raise TypeError("expected PubSpec, not %s" % type(pub_spec).__name__)
        else:
            return self._signing_overrides.get(
                str(pub_spec), self._default_signing_config
            )

    def _load_config(self, files, fail_fast=False):
        """Try to load config from the first existing file.
           Throws AptlyCtlError if options are exausted.
        """
        c = None
        for file in files:
            try:
                with open(file, "r") as f:
                    c = yaml.safe_load(f)
                    if c is None:
                        c = {}
                    logger.info('Loadded config from "%s"' % file)
            except yaml.YAMLError as e:
                raise AptlyCtlError('Invalid YAML in "{}": {}'.format(file, e)) from e
            except OSError as e:
                if e.errno in [errno.EACCES, errno.ENOENT, errno.EISDIR]:
                    if fail_fast or e.errno in [errno.EACCES, errno.EISDIR]:
                        raise AptlyCtlError(
                            'Cannot load config from "{}": {}'.format(file, e.strerror)
                        ) from e
                    else:
                        logger.debug(
                            'Cannot load config from "{}": {}'.format(file, e.strerror)
                        )
                else:
                    raise
        return c

    def _get_profile_cfg(self, cfg, profile):
        try:
            profile_list = [cfg["profiles"][int(profile)]]
        except (KeyError, TypeError) as e:
            raise AptlyCtlError("Config file must contain 'profiles' list") from e
        except IndexError as e:
            raise AptlyCtlError("There is no profile numbered %s" % profile) from e
        except ValueError:
            profile_list = [
                prof
                for prof in cfg["profiles"]
                if prof.get("name", "").startswith(profile)
            ]

        if len(profile_list) == 0:
            raise AptlyCtlError('Cannot find configuration profile "%s"' % profile)
        elif len(profile_list) > 1:
            exact_match = [
                prof for prof in profile_list if prof.get("name", "") == profile
            ]
            if len(exact_match) == 1:
                return exact_match[0]
            else:
                raise AptlyCtlError(
                    'Profile "{}" ambiguously matches {}'.format(profile, profile_list)
                )
        else:
            return profile_list[0]

    def _parse_cfg_overrides(self, cfg_overrides):
        result = dict()
        for expr in cfg_overrides:
            key, sep, val = expr.partition("=")
            if len(sep) == 0 or len(key) == 0:
                raise AptlyCtlError(
                    'Incorrect configuration key in command line arguments: "%s"' % expr
                )
            nested_set(result, key.split("."), val)
        else:
            return result
