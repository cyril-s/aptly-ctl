from . context import aptly_ctl
from aptly_ctl.utils import PackageRef, Version
import pytest
import random

class TestPackageRef:

    def test_constructor_from_aptly_key(self):
        r = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert r.prefix is None
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

    def test_constructor_from_aptly_key_without_hash(self):
        with pytest.raises(ValueError):
            r = PackageRef("Pamd64 aptly 2.2.0~rc5")

    def test_constructor_from_aptly_key_without_P(self):
        with pytest.raises(ValueError):
            r = PackageRef("amd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")

    def test_constructor_from_aptly_key_with_repo(self):
        r = PackageRef("jessie_unstable/Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert r.prefix is None
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash == "f2b7dc2061b9d95c"
        assert r.repo == "jessie_unstable"

    def test_constructor_from_direct_ref(self):
        r = PackageRef("aptly_2.2.0~rc5_amd64")
        assert r.prefix is None
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash is None
        assert r.repo is None

    def test_constructor_from_direct_ref_with_repo(self):
        r = PackageRef("jessie_unstable/aptly_2.2.0~rc5_amd64")
        assert r.prefix is None
        assert r.arch == "amd64"
        assert r.name == "aptly"
        assert r.version == Version("2.2.0~rc5")
        assert r.hash is None
        assert r.repo == "jessie_unstable"

    def test_constructor_fail_if_traling_leading_spaces(self):
        with pytest.raises(ValueError):
            r = PackageRef("   Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c ")

    def test_constructor_fail_if_traling_leading_quotes(self):
        with pytest.raises(ValueError):
            r = PackageRef('"Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"')

    def test_unsettable_attrs(self):
        r = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        attrs = ["prefix", "arch", "name", "version", "hash"]
        for attr in attrs:
            with pytest.raises(AttributeError):
                setattr(r, attr, "somevalule")

    def test_repo_is_settable(self):
        r = PackageRef("main/Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert r.repo == "main"
        r.repo = "extra"
        assert r.repo == "extra"

    def test_key_throws_exception_if_no_hash_available(self):
        with pytest.raises(TypeError) as e:
            r = PackageRef("aptly_2.2.0~rc5_amd64")
            key = r.key
        assert "cannot build aptly key becuse hash is empty" in e.value.args[0].lower()

    def test_str_returns_dir_ref_if_no_hash_available(self):
        r = PackageRef("main/aptly_2.2.0~rc5_amd64")
        assert str(r) == "aptly_2.2.0~rc5_amd64"

    def test_repr_returns_dir_ref_if_no_hash_available(self):
        r = PackageRef("main/aptly_2.2.0~rc5_amd64")
        assert repr(r) == "main/aptly_2.2.0~rc5_amd64"

    def test_str_returns_aptly_key_if_hash_is_available(self):
        r = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert str(r) == "Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"

    def test_repr_returns_aptly_key_if_hash_is_available(self):
        r = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert repr(r) == "Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"

    def test_repr_return_repo_if_it_is_available(self):
        r = PackageRef("main/Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert repr(r) == "main/Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"

    def test_constructor_from_repr(self):
        A = PackageRef("jessie_unstable/Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef(repr(A))
        assert A.prefix == B.prefix
        assert A.arch == B.arch
        assert A.name == B.name
        assert A.version == B.version
        assert A.hash == B.hash
        assert A.repo == B.repo

    def test_cmp_equlity(self):
        A = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A == B

    def test_cmp_name(self):
        A = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B
        assert B < A

    def test_cmp_architecture(self):
        A = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pi386 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A < B
        assert B > A

    def test_cmp_version(self):
        A = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 billing 2.2.0~rc6 f2b7dc2061b9d95c")
        assert A < B
        assert B > A

    def test_cmp_hash(self):
        A = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 billing 2.2.0~rc5 x2b7dc2061b9d95c")
        assert A < B
        assert B > A

    def test_cmp_emplty_hash(self):
        A = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("billing_2.2.0~rc5_amd64")
        assert A > B
        assert B < A

    def test_cmp_prefix(self):
        A = PackageRef("prefixPamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("afixPamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B
        assert B < A

    def test_cmp_empty_prefix(self):
        A = PackageRef("prefixPamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B
        assert B < A

    def test_cmp_repo(self):
        A = PackageRef("jessie_unstable/Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = PackageRef("stretch_stable/Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A == B

    def test_sort_order(self):
        ordered_list = [
                PackageRef("aptly_2.2.0~rc5_amd64"),
                PackageRef("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"),
                PackageRef("Pi386 aptly 2.2.0~rc6 f2b7dc2061b9d95c"),
                PackageRef("prefixPamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"),
                PackageRef("Pamd64 billing 2.2.0~rc5 f2b7dc2061b9d95c"),
                PackageRef("Pamd64 billing 2.2.0~rc5 x2b7dc2061b9d95c"),
                PackageRef("Pamd64 billing 2.2.0~rc6 f2b7dc2061b9d95c"),
                PackageRef("Pi386 billing 2.2.0~rc5 f2b7dc2061b9d95c"),
                ]
        shuffled_list = ordered_list[:]
        random.shuffle(shuffled_list)
        shuffled_list.sort()
        assert ordered_list == shuffled_list

