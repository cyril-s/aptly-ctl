from . context import didww_aptly_ctl
from didww_aptly_ctl.utils import PackageRef, Version
import pytest
import random

class TestPackageRef:

    def test_constructor_from_aptly_key(self):
        r = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert r.prefix == ""
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash == "f2b7dc2061b9d95c"
        assert r.repo is None

    def test_constructor_from_aptly_key_with_prefix(self):
        r = PackageRef("prefPamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert r.prefix == "pref"
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash == "f2b7dc2061b9d95c"
        assert r.repo is None

    def test_constructor_from_aptly_key_with_repo(self):
        r = PackageRef("jessie_unstable/Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert r.prefix == ""
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash == "f2b7dc2061b9d95c"
        assert r.repo == "jessie_unstable"

    def test_constructor_from_direct_ref(self):
        r = PackageRef("aptly_2.2.0~rc5_amd64")
        assert r.prefix == ""
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash == ""
        assert r.repo is None

    def test_constructor_from_direct_ref_with_repo(self):
        r = PackageRef("jessie_unstable/aptly_2.2.0~rc5_amd64")
        assert r.prefix == ""
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash == ""
        assert r.repo == "jessie_unstable"

    def test_constructor_fail_if_wrong_order_in_dir_ref(self):
        with pytest.raises(ValueError):
            r = PackageRef("aptly_amd64_2.2.0~rc5")

    def test_constructor_fail_if_traling_leading_spaces(self):
        with pytest.raises(ValueError):
            r = PackageRef("   Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c ")

    def test_constructor_fail_if_traling_leading_quotes(self):
        with pytest.raises(ValueError):
            r = PackageRef('"Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"')

    def test_constructor_repo_precedence(self):
        r = PackageRef("jessie_unstable/Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c", "stretch_repo")
        assert r.repo == "jessie_unstable"

    def test_cmp_equlity(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A == B

    def test_cmp_name(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B
        assert B < A

    def test_cmp_architecture(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pi386 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A < B
        assert B > A

    def test_cmp_version(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 didww-billing 2.2.0~rc6 f2b7dc2061b9d95c")
        assert A < B
        assert B > A

    def test_cmp_hash(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 didww-billing 2.2.0~rc5 x2b7dc2061b9d95c")
        assert A < B
        assert B > A

    def test_cmp_emplty_hash(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 didww-billing 2.2.0~rc5")
        assert A > B
        assert B < A

    def test_cmp_prefix(self):
        A = PackageRef("prefixPamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("afixPamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B
        assert B < A

    def test_cmp_empty_prefix(self):
        A = PackageRef("prefixPamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B
        assert B < A

    def test_cmp_repo(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c", "jessie_unstable")
        B = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c", "stretch_stable")
        assert A == B

    def test_sort_order(self):
        ordered_list = [
                PackageRef("Pamd64 aptly 2.2.0~rc5"),
                PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"),
                PackageRef("Pi386 aptly 2.2.0~rc6 f2b7dc2061b9d95c"),
                PackageRef("prefixPamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"),
                PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c"),
                PackageRef("Pamd64 didww-billing 2.2.0~rc5 x2b7dc2061b9d95c"),
                PackageRef("Pamd64 didww-billing 2.2.0~rc6 f2b7dc2061b9d95c"),
                PackageRef("Pi386 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c"),
                ]
        shuffled_list = ordered_list[:]
        random.shuffle(shuffled_list)
        shuffled_list.sort()
        assert ordered_list == shuffled_list

    def test_constructor_from_repr(self):
        A = PackageRef("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c", "jessie_unstable")
        B = PackageRef(repr(A))
        assert A == B
        assert A.repo == B.repo

