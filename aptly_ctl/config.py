import json
import logging
import os.path
import ast
from typing import Dict, Sequence, Any, Tuple, Optional
from aptly_ctl.aptly import SigningConfig, DefaultSigningConfig

log = logging.getLogger(__name__)


CONFIG_FILE_SUFFIXES = ("json", "conf", "cfg")
DEFAULT_CONFIG_FILE_LOCATIONS_PATTERNS: Tuple[str, ...] = ("/etc/aptly-ctl.",)

if "HOME" in os.environ:
    DEFAULT_CONFIG_FILE_LOCATIONS_PATTERNS = (
        os.path.join(os.environ["HOME"], "aptly-ctl."),
        os.path.join(os.environ["HOME"], ".aptly-ctl."),
        os.path.join(os.environ["HOME"], ".config/aptly-ctl."),
    ) + DEFAULT_CONFIG_FILE_LOCATIONS_PATTERNS

DEFAULT_CONFIG_FILE_LOCATIONS = tuple(
    file + suf
    for file in DEFAULT_CONFIG_FILE_LOCATIONS_PATTERNS
    for suf in CONFIG_FILE_SUFFIXES
)


class Config:
    url: str = "http://localhost:8090/"
    default_signing_config: SigningConfig = DefaultSigningConfig
    signing_config_map: Optional[Dict[str, SigningConfig]] = None
    connect_timeout: Optional[float] = 15.0
    read_timeout: Optional[float] = None

    def __init__(
        self, path: str = None, section: str = "", override: Dict[str, Any] = None
    ) -> None:
        config = {}
        if path:
            with open(path, "r") as file:
                # TODO handle exceptions gracefully
                config = json.load(file)
            log.info("Loaded config from %s", path)
        else:
            for try_path in DEFAULT_CONFIG_FILE_LOCATIONS:
                try:
                    with open(try_path, "r") as file:
                        config = json.load(file)
                    log.info("Loaded config from %s", try_path)
                    break
                except (FileNotFoundError, IsADirectoryError) as exc:
                    log.debug(
                        "Tried and failed to load config from %s: %s", try_path, exc
                    )

        config_section = {}
        if config:
            if section in config:
                config_section = config[section]
            else:
                config_sections = list(
                    sect for sect in config if sect.startswith(section)
                )
                if section and not config_sections:
                    raise ValueError(
                        'There is no section "{}" in {}'.format(section, list(config)),
                    )
                elif section and len(config_sections) > 1:
                    raise ValueError(
                        '"{}" is ambiguous because matches {}'.format(
                            section, config_sections
                        ),
                    )
                # from python 3.7 dict is ordered
                config_section = config[config_sections[0]]
                log.info('Selected "%s" section from configuration', config_sections[0])
        else:
            log.debug("Config file does not contain any sections")

        if not override:
            override = {}

        if "url" in override:
            self.url = override["url"]
        elif "url" in config_section:
            self.url = config_section["url"]
        else:
            log.warning('Setting url to default "%s"', self.url)

        signing_config: Dict[str, Any] = {}
        if "signing" in config_section:
            signing_config.update(config_section["signing"])
        if "signing" in override:
            signing_config.update(override["signing"])
        if signing_config:
            log.debug('Loading "signing" config')
            self.default_signing_config = SigningConfig(**signing_config)

        if "signing map" in config_section:
            signing_config_map = {}
            for key in config_section["signing map"]:
                log.debug('Loading "signing map": "%s" config', key)
                signing_config_map[key] = SigningConfig(
                    **config_section["signing map"][key]
                )
            self.signing_config_map = signing_config_map if signing_config_map else None

        if "connect_timeout" in override:
            self.connect_timeout = float(override["connect_timeout"])
        elif "connect_timeout" in config_section:
            self.connect_timeout = float(config_section["connect_timeout"])

        if "read_timeout" in override:
            self.read_timeout = float(override["read_timeout"])
        elif "read_timeout" in config_section:
            self.read_timeout = float(config_section["read_timeout"])


def parse_override_dict(keys: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key_str in keys:
        key_with_dots, _, value = key_str.partition("=")
        if not key_with_dots or not value:
            raise ValueError
        key_list = key_with_dots.split(".")
        d = out
        for key in key_list[:-1]:
            d = d.setdefault(key, {})
        # 1024 because warning in doc for ast.literal_eval says:
        # It is possible to crash the Python interpreter with a sufficiently large/complex string due to stack depth limitations in Python’s AST compiler.
        # also it hangs for a while when string is long
        if len(value) > 1024:
            d[key_list[-1]] = value
        else:
            try:
                d[key_list[-1]] = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                d[key_list[-1]] = value
    return out
