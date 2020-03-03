import pytest
from aptly_ctl.config import Config, parse_override_dict


def test_config(tmpdir):
    config_str = """
{
    "test": {
        "url": "http://example.com:8090",
        "signing": {
            "gpgkey": "aptly@example.com",
            "passphrase_file": "/home/aptly/gpg_pass"
        },
        "signing map": {
            "./unstable": {
                "skip": true
            }
        }
    }
}
    """
    config_path = tmpdir.join("aptly-ctl.json")
    with open(config_path, "w") as file:
        file.write(config_str)

    config = Config(config_path)
    assert config.url == "http://example.com:8090"
    assert config.default_signing_config.gpgkey == "aptly@example.com"
    assert config.default_signing_config.passphrase_file == "/home/aptly/gpg_pass"
    assert "./unstable" in config.signing_config_map
    assert config.signing_config_map["./unstable"].skip is True

    config = Config(
        config_path,
        override={
            "url": "http://localhost:8090",
            "signing": {"gpgkey": "root@localhost"},
        },
    )
    assert config.url == "http://localhost:8090"
    assert config.default_signing_config.gpgkey == "root@localhost"
    assert config.default_signing_config.passphrase_file == "/home/aptly/gpg_pass"
    assert "./unstable" in config.signing_config_map
    assert config.signing_config_map["./unstable"].skip is True


def test_config_section_selection(tmpdir):
    config_str = """
{
    "test": {
        "url": "http://example.com:8091"
    },
    "test2": {
        "url": "http://example.com:8092"
    }
}
    """
    config_path = tmpdir.join("aptly-ctl.json")
    with open(config_path, "w") as file:
        file.write(config_str)

    with pytest.raises(ValueError) as exc:
        config = Config(config_path, "tes")
    assert "ambiguous" in str(exc)

    with pytest.raises(ValueError) as exc:
        config = Config(config_path, "bla")
    assert "no section" in str(exc)

    config = Config(config_path, "test")
    assert config.url == "http://example.com:8091"

    config = Config(config_path, "test2")
    assert config.url == "http://example.com:8092"


def test_parse_override_dict():
    inp = [
        "url=http://localhost:8080",
        "signing.skip=True",
        "some.nested.int=1",
        "float=1.2",
        "too long=" + "1" * 1000000,
    ]
    expected = {
        "url": "http://localhost:8080",
        "signing": {"skip": True},
        "some": {"nested": {"int": 1}},
        "float": 1.2,
        "too long": "1" * 1000000,
    }
    assert parse_override_dict(inp) == expected
