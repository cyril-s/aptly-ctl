import pytest  # type: ignore
from aptly_ctl.debian import Version


class TestVersion:
    def test_init_err(self):
        for v in [
            "1.0-ю3",  # non ascii
            "-1:1.0",  # negative epoch
            "1a:1.0",  # non decimal epoch
            "1:-1",  # empty upstream version
            "1.1-",  # empty revision
            ":1.1",  # empty epoch
            "a1.0-1",  # upstream version starts with non decimal
        ]:
            with pytest.raises(ValueError):
                Version(v)

    def test_cmp_distinct(self):
        for left, right in [
            ("1:1.0", "2:1.0"),  # epoch cmp nonzero
            ("0:1.0", "1:1.0"),  # epoch cmp zero with nonzero
            ("1.0", "1:1.0"),  # epoch cmp empty with nonzero
            ("1.2", "1.10"),  # upsream ver cmp numeric order
            ("1.2.ananas", "1.2.apple"),  # upsream ver cmp alphabet order
            ("1.2", "1.2.1"),  # upsream ver cmp empty vs non decimal part
            ("1.2", "1.2.0"),  # dpkg --compare-versions 1.2 eq 1.2.0 exits with 1
            ("1.2~1", "1.2"),  # upsream ver cmp tilde erlier then empty
            ("1.2~1", "1.2-1"),  # upsream ver cmp tilde erlier then anything
            ("1.1-1", "1.1-2"),  # revision cmp numeric order
            ("1.2-1a", "1.2-1b"),  # revision cmp alphabet order
            ("1.2", "1.2-1"),  # revision cmp empty vs something
            ("1.2-1~a", "1.2-1"),  # revision cmp tilde erlier then empty
            ("1.2-1~1", "1.2-1a"),  # revision cmp tilde erlier then anything
        ]:
            assert Version(left) < Version(right) and Version(right) > Version(left)
            assert hash(Version(left)) != hash(Version(right))

    def test_cmp_same(self):
        for left, right in [
            ("1.0", "0:1.0"),  # epoch cmp empty with_zero
            ("1.2.", "1.2.0"),  # upsream ver cmp empty vs decimal part
            ("1.2-bla", "1.2-bla0"),  # revision cmp empty vs decimal part
            ("1.2", "1.2-0"),  # revision cmp empty vs zero
        ]:
            assert Version(left) == Version(right)
            assert hash(Version(left)) == hash(Version(right))

    def test_str_repr(self):
        for ver, rep in [
            ("1.0", "0:1.0-0"),
            ("0:1.0", "0:1.0-0"),
            ("1.0-0", "0:1.0-0"),
            ("0:1.0-0", "0:1.0-0"),
        ]:
            v = Version(ver)
            assert str(v) == ver
            assert repr(v) == rep
