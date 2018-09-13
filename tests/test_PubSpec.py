from . context import aptly_ctl
from aptly_ctl.utils import PubSpec
import pytest

class TestPubSpec:

    def test_init_with_distribution_and_prefix(self):
        p = PubSpec(distribution="stretch", prefix="debian")
        assert p.distribution == "stretch"
        assert p.prefix == "debian"
        assert repr(p) == "debian/stretch"
        assert str(p) == "debian/stretch"

    def test_init_with_distribution(self):
        p = PubSpec(distribution="stretch")
        assert p.distribution == "stretch"
        assert p.prefix == "."
        assert repr(p) == "./stretch"
        assert str(p) == "./stretch"

    def test_init_with_prefix_in_distribution(self):
        p = PubSpec("debian/stretch")
        assert p.distribution == "stretch"
        assert p.prefix == "debian"
        assert repr(p) == "debian/stretch"
        assert str(p) == "debian/stretch"

    def test_init_ignore_prefix_when_prefix_in_distribution(self):
        p = PubSpec("debian/stretch", prefix="ubuntu")
        assert p.distribution == "stretch"
        assert p.prefix == "debian"
        assert repr(p) == "debian/stretch"
        assert str(p) == "debian/stretch"

    def test_init_malformed_distribution_with_prefix(self):
        with pytest.raises(ValueError):
            p = PubSpec("/stretch")
        with pytest.raises(ValueError):
            p = PubSpec("debian/")
        with pytest.raises(ValueError):
            p = PubSpec("/")

    def test_attributes_unsettable(self):
        p = PubSpec("debian/stretch")
        for attr in ["distribution", "prefix"]:
            with pytest.raises(AttributeError):
                setattr(p, attr, "somevalule")

    def test_prefix_with_slashes(self):
        p = PubSpec("public/debian/stretch")
        assert p.distribution == "stretch"
        assert p.prefix == "public/debian"
        assert repr(p) == "public/debian/stretch"
        assert str(p) == "public/debian/stretch"


