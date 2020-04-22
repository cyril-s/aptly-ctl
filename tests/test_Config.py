from . context import aptly_ctl
from aptly_ctl.exceptions import AptlyCtlError
from aptly_ctl.Config import Config
from aptly_ctl.utils import PubSpec
import pytest
import os
import yaml

class TestConfig:

    _goodConfig = {
        "profiles": [
            {
                "name": "profile0",
                "url": "http://localhost:8090/api",
                "signing": {
                    "gpgkey": "aba45rts",
                    "passphrase": "passphrase"
                }
            },
            {
                "name": "profile1",
                "url": "http://localhost:8080/api",
                "signing": {
                    "gpgkey": "xxxxxxxx",
                    "passphrase": "xxxxxxxxx"
                }
            },
            {
                "name": "my_profile",
                "url": "http://localhost:8070/api",
                "signing": {
                    "gpgkey": "yyyyyyyyy",
                    "passphrase": "yyyyyyyy"
                }
            },
            {
                "name": "prefix",
                "url": "http://localhost:8071/api",
                "signing": {
                    "gpgkey": "xxxxxxxxx",
                    "passphrase": "xxxxxxxxx"
                }
            },
            {
                "name": "prefix2",
                "url": "http://localhost:8072/api",
                "signing": {
                    "gpgkey": "zzzzzzzzz",
                    "passphrase": "zzzzzzzzz"
                }
            },
            {
                "name": "with_signing_overrides",
                "url": "http://somehost:8090/api",
                "signing": {
                    "gpgkey": "default",
                    "passphrase": "default"
                },
                "signing_overrides": {
                    "./stretch": {
                        "gpgkey": "stretch",
                        "passphrase": "stretch"
                    },
                    "debian/jessie": {
                        "gpgkey": "jessie",
                        "passphrase": "jessie"
                    }
                }
            },
            {
                "name": "with_empty_passphrase",
                "url": "http://somehost:8090/api",
                "signing": {
                    "gpgkey": "foobar",
                    "passphrase": ""
                },
            },
            {
                "name": "with_empty_passphrase_file",
                "url": "http://somehost:8090/api",
                "signing": {
                    "gpgkey": "foobar",
                    "passphrase": ""
                },
            }
        ]
    }

    @pytest.fixture
    def goodConfigPath(self, tmpdir):
        import yaml
        path_to_file = tmpdir.join("aptly-ctl.conf")
        config = self._goodConfig.copy()
        with open(path_to_file, "w") as f:
            yaml.dump(config, f)
        return path_to_file


    def test_config_init_nonexistent_path(self, tmpdir):
        with pytest.raises(AptlyCtlError) as e:
            c = Config(tmpdir.join("nonexistent.conf"))
        assert "no such file or directory" in e.value.args[0].lower()

    def test_config_init_from_directory(self, tmpdir):
        with pytest.raises(AptlyCtlError) as e:
            c = Config(tmpdir)
        assert "is a directory" in e.value.args[0].lower()

    def test_config_init_no_permissions(self, tmpdir):
        path = tmpdir.join("not_readable.conf")
        with open(path, 'w') as f:
            os.chmod(f.fileno(), 0)
        with pytest.raises(AptlyCtlError) as e:
            c = Config(path)
        assert "permission denied" in e.value.args[0].lower()

    def test_config_init_invalid_yaml(self, tmpdir):
        path = tmpdir.join("invalid.yaml")
        with open(path, 'w') as f:
            f.write("%invalid yaml!")
        with pytest.raises(AptlyCtlError) as e:
            c = Config(path)
        assert "invalid yaml" in e.value.args[0].lower()

    def test_config_init_existent_path(self, goodConfigPath):
        assert Config(goodConfigPath).name == "profile0"

    def test_config_init_set_profile_by_int(self, goodConfigPath):
        assert Config(goodConfigPath, 1).name == "profile1"

    def test_config_init_set_profile_by_name(self, goodConfigPath):
        c = Config(goodConfigPath, "profile1")
        assert c.name == "profile1"
        assert c.url == self._goodConfig["profiles"][1]["url"]

    def test_config_init_set_profile_by_partial_name(self, goodConfigPath):
        c = Config(goodConfigPath, "my")
        assert c.name == "my_profile"
        assert c.url == self._goodConfig["profiles"][2]["url"]

    def test_config_init_without_profiles(self, tmpdir):
        path = tmpdir.join("empty.conf")
        with open(path, 'w'):
            pass
        with pytest.raises(AptlyCtlError) as e:
            c = Config(path)
        assert "config file must contain 'profiles' list" in e.value.args[0].lower()

    def test_config_init_set_profile_wrong_num(self, goodConfigPath):
        with pytest.raises(AptlyCtlError) as e:
            c = Config(goodConfigPath, 55)
        assert "there is no profile numbered" in e.value.args[0].lower()

    def test_config_init_set_profile_ambiguous_name(self, goodConfigPath):
        with pytest.raises(AptlyCtlError) as e:
            c = Config(goodConfigPath, "profile")
        assert "ambiguously matches" in e.value.args[0].lower()

    def test_config_init_set_profile_ambiguous_name_but_matches_fully(self, goodConfigPath):
        c = Config(goodConfigPath, "prefix")
        assert c.name == "prefix"
        assert c.url == self._goodConfig["profiles"][3]["url"]

    def test_config_init_set_profile_wrong_name(self, goodConfigPath):
        with pytest.raises(AptlyCtlError) as e:
            c = Config(goodConfigPath, "nonexistent")
        assert "cannot find configuration profile" in e.value.args[0].lower()

    def test_config_init_cfg_overrides(self, goodConfigPath):
        url = "http://1.1.1.1:11"
        gpgkey =  "111111"
        c = Config(goodConfigPath, 0, ["url=%s" % url, "signing.gpgkey=%s" % gpgkey])
        assert c.url == url
        assert c.get_signing_config().gpgkey == gpgkey
        assert c.name == "profile0"

    def test_config_init_cfg_overrides_wrong_key(self, goodConfigPath):
        url = "url http://localhost:9090/api"
        with pytest.raises(AptlyCtlError) as e:
            c = Config(goodConfigPath, 0, [url])
        assert "incorrect configuration key in command line arguments" in e.value.args[0].lower()

    def test_cfg_no_url(self, tmpdir):
        wrong_cfg = {}
        wrong_cfg["profiles"] = [ self._goodConfig["profiles"][0].copy() ]
        del wrong_cfg["profiles"][0]["url"]
        path_to_wrong_cfg = tmpdir.join("aptly-ctl-wrong.conf")
        with open(path_to_wrong_cfg, 'a') as f:
            yaml.dump(wrong_cfg, f)
        with pytest.raises(AptlyCtlError) as e:
            c = Config(path_to_wrong_cfg)
        assert "specify url of api to connect to" in e.value.args[0].lower()

    def test_init_no_cfg_only_overrides(self):
        url = "http://1.1.1.1:11"
        gpgkey =  "111111"
        passphrase_file = "/etc/passphrase"
        cfg_overrides = [
                "url=%s" % url,
                "signing.gpgkey=%s" % gpgkey,
                "signing.passphrase_file=%s" % passphrase_file
                ]
        c = Config(False, cfg_overrides=cfg_overrides)
        assert c.url == url
        assert c.get_signing_config().gpgkey == gpgkey
        assert c.get_signing_config().passphrase_file == passphrase_file
        assert hasattr(c, "name") is False

    def test_get_overrided_signing_config(self, goodConfigPath):
        c = Config(goodConfigPath, "with_sign")
        assert c.get_signing_config().gpgkey == "default"
        assert c.get_signing_config(PubSpec("./stretch")).gpgkey == "stretch"
        assert c.get_signing_config(PubSpec("debian/jessie")).gpgkey == "jessie"
        assert c.get_signing_config(PubSpec("none/none")).gpgkey == "default"

    def test_get_overrided_signing_config_if_there_are_no_signing_overrides(self, goodConfigPath):
        c = Config(goodConfigPath, 0)
        assert c.get_signing_config().gpgkey == "aba45rts"
        assert c.get_signing_config(PubSpec("./stretch")).gpgkey == "aba45rts"

