from . context import didww_aptly_ctl
from didww_aptly_ctl.Config import SigningConfig
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError
import pytest

class TestSigningConfig:

    signning_config_attrs = [
            "skip",
            "batch",
            "gpgkey",
            "keyring",
            "secret_keyring",
            "passphrase",
            "passphrase_file"
            ]

    def test_signing_config_has_necessary_attrs(self):
        c = SigningConfig(gpgkey="xxx", passphrase="password")
        for attr in self.signning_config_attrs:
            assert hasattr(c, attr) is True

    def test_signing_config_attrs_unsettable(self):
        c = SigningConfig(gpgkey="xxx", passphrase="password")
        for attr in self.signning_config_attrs:
            with pytest.raises(AttributeError):
                setattr(c, attr, "somevalule")

    def test_signing_config_as_dict_method(self):
        d_reference = {
            "skip": False,
            "batch": True,
            "gpgkey": "xxx",
            "keyring": None,
            "secret_keyring": None,
            "passphrase": "password",
            "passphrase_file": None
            }
        c = SigningConfig(**d_reference)
        d = c.as_dict()
        assert d == d_reference

    def test_signing_config_as_dict_method_with_prefix(self):
        d_init = {
            "skip": False,
            "batch": True,
            "gpgkey": "xxx",
            "keyring": None,
            "secret_keyring": None,
            "passphrase": "password",
            "passphrase_file": None
            }
        d_reference = {}
        for k, v in d_init.items():
            d_reference["sign_" + k] = v
        c = SigningConfig(**d_init)
        d = c.as_dict(prefix="sign_")
        assert d == d_reference

    def test_signing_config_no_gpgkey(self):
        with pytest.raises(DidwwAptlyCtlError):
            c = SigningConfig(skip=False, passphrase="password")

    def test_signing_config_both_passphrase_passphrase_file(self):
        with pytest.raises(DidwwAptlyCtlError):
            c = SigningConfig(
                    skip=False,
                    gpgkey="xxx",
                    passphrase="password",
                    passphrase_file="pass_file")

    def test_signing_config_none_passphrase_passphrase_file(self):
        with pytest.raises(DidwwAptlyCtlError):
            c = SigningConfig(skip=False, gpgkey="xxx")

    def test_signing_config_skip_true(self):
        assert SigningConfig(skip=True) is not None

    def test_signing_config_unknown_key_arg(self):
        with pytest.raises(DidwwAptlyCtlError) as e:
            c = SigningConfig(skip=True, unknown="unknown")
        assert "unknown configuration keys: ['unknown=unknown']" in e.value.args[0].lower()
