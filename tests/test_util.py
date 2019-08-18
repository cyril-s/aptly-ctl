import pytest
from aptly_ctl.util import rotate, DebianVersion
import aptly_api
from aptly_ctl.types import Package


def pkg(*args):
    return Package.from_aptly_api(aptly_api.Package(*args))


def test_rotate():
    inp1 = [
            pkg("Pamd64 python 3.6.6 3660000000000000", None, None, None),
            pkg("Pamd64 python 3.6.5 3650000000000000", None, None, None),
            pkg("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
            pkg("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
            pkg("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
            pkg("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
            pkg("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
            ]
    for inp, n, exp in [
            (
                inp1,
                2,
                [
                    pkg("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.4.0 1400000000000000", None, None, None),
                    ],
                ),
            (
                inp1,
                -2,
                [
                    pkg("Pamd64 aptly 1.5.0 1500000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.6.0 1500000000000000", None, None, None),
                    pkg("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                    pkg("Pamd64 python 3.6.6 3660000000000000", None, None, None),
                    ],
                ),
            (
                inp1,
                0,
                inp1,
                ),
            (
                inp1,
                len(inp1),
                [],
                ),
            (
                inp1,
                -len(inp1),
                inp1,
                ),
            (
                [
                    pkg("Pamd64 python 3.6.6 3660000000000000", None, None, None),
                    pkg("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                    pkg("Pi386 python 3.6.6 3660000000000000", None, None, None),
                    pkg("Pi386 python 3.6.5 3650000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
                    pkg("Pi386 aptly 1.3.0 1300000000000000", None, None, None),
                    pkg("Pi386 aptly 1.2.0 1200000000000000", None, None, None),
                    ],
                1,
                [
                    pkg("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("Pi386 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                    pkg("Pi386 python 3.6.5 3650000000000000", None, None, None),
                    ]
                ),
            (
                [
                    pkg("Pamd64 python 3.6.6 3660000000000000", None, None, None),
                    pkg("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("prefPamd64 aptly 1.3.0 1300000000000000", None, None, None),
                    pkg("prefPamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("Pamd64 aptly 1.3.0 1300000000000000", None, None, None),
                    pkg("somePamd64 python 3.6.6 3660000000000000", None, None, None),
                    pkg("somePamd64 python 3.6.5 3650000000000000", None, None, None),
                    ],
                1,
                [
                    pkg("Pamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("prefPamd64 aptly 1.2.0 1200000000000000", None, None, None),
                    pkg("Pamd64 python 3.6.5 3650000000000000", None, None, None),
                    pkg("somePamd64 python 3.6.5 3650000000000000", None, None, None),
                    ]
                ),
            ([], 2, []),
            ([], -2, []),
            ([], 0, []),
            ]:
        result = rotate("{o.prefix}{o.arch}{o.name}", lambda x: x.version, n, inp)
        assert len(result) == len(exp)
        for x in result:
            assert x in exp


class TestDebianVersion:

    def test_init_err(self):
        for v in [
                "1.0-ю3", # non ascii
                "-1:1.0", # negative epoch
                "1a:1.0", # non decimal epoch
                "1:-1", # empty upstream version
                "1.1-", # empty revision
                ":1.1", # empty epoch
                "a1.0-1", # upstream version starts with non decimal
                ]:
            with pytest.raises(ValueError):
                DebianVersion(v)

    def test_cmp_distinct(self):
        for left, right in [
                ("1:1.0", "2:1.0"),     # epoch cmp nonzero
                ("0:1.0", "1:1.0"),     # epoch cmp zero with nonzero
                ("1.0", "1:1.0"),       # epoch cmp empty with nonzero
                ("1.2", "1.10"),        # upsream ver cmp numeric order
                ("1.2.ananas", "1.2.apple"), # upsream ver cmp alphabet order
                ("1.2", "1.2.1"),       # upsream ver cmp empty vs non decimal part
                ("1.2", "1.2.0"),       # dpkg --compare-versions 1.2 eq 1.2.0 exits with 1
                ("1.2~1", "1.2"),       # upsream ver cmp tilde erlier then empty
                ("1.2~1", "1.2-1"),     # upsream ver cmp tilde erlier then anything
                ("1.1-1", "1.1-2"),     # revision cmp numeric order
                ("1.2-1a", "1.2-1b"),   # revision cmp alphabet order
                ("1.2", "1.2-1"),       # revision cmp empty vs something
                ("1.2-1~a", "1.2-1"),   # revision cmp tilde erlier then empty
                ("1.2-1~1", "1.2-1a"),  # revision cmp tilde erlier then anything
                ]:
            assert DebianVersion(left) < DebianVersion(right) \
                    and DebianVersion(right) > DebianVersion(left)
            assert hash(DebianVersion(left)) != hash(DebianVersion(right))

    def test_cmp_same(self):
        for left, right in [
                ("1.0", "0:1.0"), # epoch cmp empty with_zero
                ("1.2.", "1.2.0"), # upsream ver cmp empty vs decimal part
                ("1.2-bla", "1.2-bla0"), # revision cmp empty vs decimal part
                ("1.2", "1.2-0"), # revision cmp empty vs zero
                ]:
            assert DebianVersion(left) == DebianVersion(right)
            assert hash(DebianVersion(left)) == hash(DebianVersion(right))

    def test_str_repr(self):
        for ver, rep in [
                ("1.0", "0:1.0-0"),
                ("0:1.0", "0:1.0-0"),
                ("1.0-0", "0:1.0-0"),
                ("0:1.0-0", "0:1.0-0"),
                ]:
            v = DebianVersion(ver)
            assert str(v) == ver
            assert repr(v) == rep
