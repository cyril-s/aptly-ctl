from . context import aptly_ctl
import pytest
import aptly_api


publishes = [
    aptly_api.PublishEndpoint(
        storage=None,
        prefix=".",
        distribution="stretch",
        source_kind="local",
        sources=[
            {
                "Component": "main",
                "Name": "stretch_main"
            },
            {
                "Component": "extra",
                "Name": "stretch_extra"
            }
        ],
        architectures=["amd64"],
        label=None,
        origin=""
    ),
    aptly_api.PublishEndpoint(
        storage=None,
        prefix=".",
        distribution="buster",
        source_kind="local",
        sources=[
            {
                "Component": "main",
                "Name": "buster_main"
            },
            {
                "Component": "extra",
                "Name": "buster_extra"
            }
        ],
        architectures=["amd64"],
        label=None,
        origin=None
    ),
]


@pytest.fixture(scope="module")
def config():
    cfg_overrides = [
            "url=http://localhost:8090",
            "signing.gpgkey=111111",
            "signing.passphrase_file=/etc/pass"
            ]
    return aptly_ctl.Config.Config(False, cfg_overrides=cfg_overrides)


@pytest.fixture(autouse=True)
def no_requests(monkeypatch):
    monkeypatch.delattr("requests.sessions.Session.request")


@pytest.fixture(scope="module")
def mocked_publish_list():
    return lambda *args, **kwargs: publishes


def test_lookup_publish_by_repos_using_Repo(config, monkeypatch, mocked_publish_list):
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "list", mocked_publish_list)
    aptly = aptly_ctl.utils.ExtendedAptlyClient(config.url)
    l = aptly.lookup_publish_by_repos([
        aptly_api.Repo("stretch_main", None, None, None),
        aptly_api.Repo("stretch_extra", None, None, None),
        ])
    assert len(l) == 1
    assert l[0] == publishes[0]


def test_lookup_publish_by_repos_using_strings(config, monkeypatch, mocked_publish_list):
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "list", mocked_publish_list)
    aptly = aptly_ctl.utils.ExtendedAptlyClient(config.url)
    l = aptly.lookup_publish_by_repos(["buster_main", "buster_extra"])
    assert len(l) == 1
    assert l[0] == publishes[1]


def test_update_dependent_publishes(config, monkeypatch, mocked_publish_list):
    def _publish_update(*args, **kwargs):
        return publishes
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "list", mocked_publish_list)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "update", _publish_update)
    aptly = aptly_ctl.utils.ExtendedAptlyClient(config.url)
    exc = aptly.update_dependent_publishes(["streth_main", "buster_main"], config)
    assert len(exc) == 0


def test_update_dependent_publishes_return_exception_on_fail(config, monkeypatch, mocked_publish_list):
    def _publish_update(*args, **kwargs):
        if kwargs["prefix"] == "." and kwargs["distribution"] == "stretch":
            return publishes[0]
        else:
            raise aptly_api.AptlyAPIException("Internal server error", status_code=500)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "list", mocked_publish_list)
    monkeypatch.setattr(aptly_api.parts.publish.PublishAPISection, "update", _publish_update)
    aptly = aptly_ctl.utils.ExtendedAptlyClient(config.url)
    exc = aptly.update_dependent_publishes(["streth_main", "buster_main"], config)
    assert len(exc) == 1
    assert exc[0].status_code == 500
