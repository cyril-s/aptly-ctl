from . context import aptly_ctl
from aptly_api.parts.packages import Package
from aptly_ctl.subcommands.search import rotate
from aptly_ctl.utils import PackageRef

class TestSearchSubcommand:

    def test_rotate_positive(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 2)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_negative(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, -2)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_zero(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 0)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_different_architectures(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 1)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pi386 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_different_prefixes(self):
        a = [
                Package(key="Pamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="prefPamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="prefPamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="somePamd64 python 3.6.6 3660000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="somePamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 1)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="prefPamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="somePamd64 python 3.6.5 3650000000000000", short_key=None, files_hash=None, fields=None),
                ]

    def test_rotate_positive_out_of_range(self):
        a = [
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, 10)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == []

    def test_rotate_negative_out_of_range(self):
        a = [
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
        b = rotate(a, -10)
        b.sort(key=lambda s: PackageRef(s.key))
        assert b == [
                Package(key="Pamd64 aptly 1.2.0 1200000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.3.0 1300000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.4.0 1400000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.5.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                Package(key="Pamd64 aptly 1.6.0 1500000000000000", short_key=None, files_hash=None, fields=None),
                ]
