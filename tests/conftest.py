import pytest

@pytest.fixture
def no_requests(monkeypatch):
    monkeypatch.delattr("requests.sessions.Session.request")
