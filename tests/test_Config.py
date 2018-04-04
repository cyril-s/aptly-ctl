from . context import didww_aptly_ctl
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
from didww_aptly_ctl.Config import Config
import pytest

class TestConfig:

    _goodConfig = {
        "profiles": [
            {
                "name": "profile0",
                "url": "http://localhost:8090/api",
                "signing": {
                    "gpg_key": "aba45rts",
                    "passphrase": "passphrase"
                }
            },
            {
                "name": "profile1",
                "url": "http://localhost:8080/api",
                "signing": {
                    "gpg_key": "xxxxxxxx",
                    "passphrase": "xxxxxxxxx"
                }
            },
            {
                "name": "my_profile",
                "url": "http://localhost:8070/api",
                "signing": {
                    "gpg_key": "yyyyyyyyy",
                    "passphrase": "yyyyyyyy"
                }
            }
        ]
    }


    @pytest.fixture
    def dummyConfig(self):
        class _dummyConfig(Config):
            def __init__(self):
                pass
        return _dummyConfig()


    @pytest.fixture
    def goodConfig(self, tmpdir):
        import yaml
        path_to_file = tmpdir.join("aptly-ctl.conf")
        config = self._goodConfig.copy()
        with open(path_to_file, "w") as f:
            yaml.dump(config, f)
        return path_to_file


    def test_loading_nonexistent_config(self, tmpdir, dummyConfig):
        with pytest.raises(DidwwAptlyCtlError):
            c = dummyConfig._load_config(tmpdir.join("aptly-ctl.conf"))


    def test_loading_existent_config(self, goodConfig, dummyConfig):
        c = dummyConfig._load_config(goodConfig)
        assert c is not None
        assert len(c) > 0


    def test_get_profile_by_num(self, dummyConfig):
        c = dummyConfig._get_profile_cfg(self._goodConfig, 0)
        assert c is self._goodConfig["profiles"][0]


    def test_get_profile_by_name(self, dummyConfig):
        c = dummyConfig._get_profile_cfg(self._goodConfig, "profile0")
        assert c is self._goodConfig["profiles"][0]


    def test_get_profile_by_partial_name(self, dummyConfig):
        c = dummyConfig._get_profile_cfg(self._goodConfig, "my")
        assert c is self._goodConfig["profiles"][2]


    def test_config_without_profiles(self, dummyConfig):
        with pytest.raises(DidwwAptlyCtlError):
            c = dummyConfig._get_profile_cfg(dict(), 0)


    def test_get_profile_by_wrong_num(self, dummyConfig):
        with pytest.raises(DidwwAptlyCtlError):
            c = dummyConfig._get_profile_cfg(self._goodConfig, 55)


    def test_get_profile_by_ambiguous_name(self, dummyConfig):
        with pytest.raises(DidwwAptlyCtlError):
            c = dummyConfig._get_profile_cfg(self._goodConfig, "profile")


    def test_get_profile_by_wrong_name(self, dummyConfig):
        with pytest.raises(DidwwAptlyCtlError):
            c = dummyConfig._get_profile_cfg(self._goodConfig, "nonexistent")


    def test_cfg_overrides(self, dummyConfig):
        result = {
            "url": "http://overriden/api",
            "signing": {
                "gpg_key": "ABCDEFG",
                "passphrase": "pass=phrase",
            },
        }
        cmd_overrides = [
            "url=%s" % result["url"],
            "signing.gpg_key=%s" % result["signing"]["gpg_key"],
            "signing.passphrase=%s" % result["signing"]["passphrase"],
        ]
        c = dummyConfig._parse_cmd_line_overrides(cmd_overrides)
        assert c == result


    def test_cfg_overrides_wrong_key(self, dummyConfig):
        cmd_overrides = ["url http://localhost:9090/api"]
        with pytest.raises(DidwwAptlyCtlError):
            c = dummyConfig._parse_cmd_line_overrides(cmd_overrides)
            