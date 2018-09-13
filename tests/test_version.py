from . context import aptly_ctl
from aptly_ctl.utils import Version
import pytest

class TestVersion(object):
    # Test costructor
    def test_version_constructor_non_ascii(self):
        with pytest.raises(ValueError):
            v = Version("1.0-ю3")

    def test_version_constructor_err_on_negative_epoch(self):
        with pytest.raises(ValueError):
            v = Version("-1:1.0")

    def test_version_constructor_err_on_non_decimal_epoch(self):
        with pytest.raises(ValueError):
            v = Version("1a:1.0")

    def test_version_constructor_err_on_empty_upstream_version(self):
        with pytest.raises(ValueError):
            v = Version("1:-1")

    def test_version_constructor_err_on_empty_revision(self):
        with pytest.raises(ValueError):
            v = Version("1.1-")

    def test_version_constructor_err_on_empty_epoch(self):
        with pytest.raises(ValueError):
            v = Version(":1.1")

    def test_version_constructor_err_on_upstream_version_starts_with_non_decimal(self):
        with pytest.raises(ValueError):
            v = Version("a1.0-1")

    # Test epoch comparison
    def test_epoch_cmp_nonzero(self):
        A = Version("1:1.0")
        B = Version("2:1.0")
        assert A < B and B > A

    def test_epoch_cmp_zero_with_nonzero(self):
        A = Version("0:1.0")
        B = Version("1:1.0")
        assert A < B and B > A

    def test_epoch_cmp_empty_with_nonzero(self):
        A = Version("1.0")
        B = Version("1:1.0")
        assert A < B and B > A

    def test_epoch_cmp_empty_with_zero(self):
        A = Version("1.0")
        B = Version("0:1.0")
        assert A == B

    # Test upstream version comparison
    def test_upsream_ver_cmp_numeric_order(self):
        A = Version("1.2")
        B = Version("1.10")
        assert A < B and B > A

    def test_upsream_ver_cmp_alphabet_order(self):
        A = Version("1.2.ananas")
        B = Version("1.2.apple")
        assert A < B and B > A

    def test_upsream_ver_cmp_empty_vs_non_decimal_part(self):
        A = Version("1.2")
        B = Version("1.2.1")
        assert A < B and B > A

    def test_upsream_ver_cmp_empty_vs_decimal_part(self):
        A = Version("1.2.")
        B = Version("1.2.0")
        assert A == B

    def test_upsream_ver_cmp_tilde_erlier_then_empty(self):
        A = Version("1.2~1")
        B = Version("1.2")
        assert A < B and B > A

    def test_upsream_ver_cmp_tilde_erlier_then_anything(self):
        A = Version("1.2~1")
        B = Version("1.2-1")
        assert A < B and B > A

    # Test revision number comparison
    def test_revision_cmp_numeric_order(self):
        A = Version("1.1-1")
        B = Version("1.1-2")
        assert A < B and B > A

    def test_revision_cmp_alphabet_order(self):
        A = Version("1.2-1a")
        B = Version("1.2-1b")
        assert A < B and B > A

    def test_revision_cmp_empty_vs_something(self):
        A = Version("1.2")
        B = Version("1.2-1")
        assert A < B and B > A

    def test_revision_cmp_empty_vs_zero(self):
        A = Version("1.2")
        B = Version("1.2-0")
        assert A == B

    def test_revision_cmp_tilde_erlier_then_empty(self):
        A = Version("1.2-1~a")
        B = Version("1.2-1")
        assert A < B and B > A

    def test_revision_cmp_tilde_erlier_then_anything(self):
        A = Version("1.2-1~1")
        B = Version("1.2-1a")
        assert A < B and B > A

