from datetime import timedelta
from aptly_ctl.util import rotate, urljoin, timedelta_pretty
from aptly_ctl.aptly import Package


def test_rotate():
    inp1 = [
        Package.from_key("Pamd64 python 3.6.6 3660000000000000"),
        Package.from_key("Pamd64 python 3.6.5 3650000000000000"),
        Package.from_key("Pamd64 aptly 1.5.0 1500000000000000"),
        Package.from_key("Pamd64 aptly 1.3.0 1300000000000000"),
        Package.from_key("Pamd64 aptly 1.2.0 1200000000000000"),
        Package.from_key("Pamd64 aptly 1.4.0 1400000000000000"),
        Package.from_key("Pamd64 aptly 1.6.0 1500000000000000"),
    ]
    for inp, n, exp in [
        (
            inp1,
            2,
            [
                Package.from_key("Pamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("Pamd64 aptly 1.3.0 1300000000000000"),
                Package.from_key("Pamd64 aptly 1.4.0 1400000000000000"),
            ],
        ),
        (
            inp1,
            -2,
            [
                Package.from_key("Pamd64 aptly 1.5.0 1500000000000000"),
                Package.from_key("Pamd64 aptly 1.6.0 1500000000000000"),
                Package.from_key("Pamd64 python 3.6.5 3650000000000000"),
                Package.from_key("Pamd64 python 3.6.6 3660000000000000"),
            ],
        ),
        (inp1, 0, inp1,),
        (inp1, len(inp1), [],),
        (inp1, -len(inp1), inp1,),
        (
            [
                Package.from_key("Pamd64 python 3.6.6 3660000000000000"),
                Package.from_key("Pamd64 python 3.6.5 3650000000000000"),
                Package.from_key("Pi386 python 3.6.6 3660000000000000"),
                Package.from_key("Pi386 python 3.6.5 3650000000000000"),
                Package.from_key("Pamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("Pamd64 aptly 1.3.0 1300000000000000"),
                Package.from_key("Pi386 aptly 1.3.0 1300000000000000"),
                Package.from_key("Pi386 aptly 1.2.0 1200000000000000"),
            ],
            1,
            [
                Package.from_key("Pamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("Pi386 aptly 1.2.0 1200000000000000"),
                Package.from_key("Pamd64 python 3.6.5 3650000000000000"),
                Package.from_key("Pi386 python 3.6.5 3650000000000000"),
            ],
        ),
        (
            [
                Package.from_key("Pamd64 python 3.6.6 3660000000000000"),
                Package.from_key("Pamd64 python 3.6.5 3650000000000000"),
                Package.from_key("Pamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("prefPamd64 aptly 1.3.0 1300000000000000"),
                Package.from_key("prefPamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("Pamd64 aptly 1.3.0 1300000000000000"),
                Package.from_key("somePamd64 python 3.6.6 3660000000000000"),
                Package.from_key("somePamd64 python 3.6.5 3650000000000000"),
            ],
            1,
            [
                Package.from_key("Pamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("prefPamd64 aptly 1.2.0 1200000000000000"),
                Package.from_key("Pamd64 python 3.6.5 3650000000000000"),
                Package.from_key("somePamd64 python 3.6.5 3650000000000000"),
            ],
        ),
        ([], 2, []),
        ([], -2, []),
        ([], 0, []),
    ]:
        result = rotate("{o.prefix}{o.arch}{o.name}", lambda x: x.version, n, inp)
        assert len(result) == len(exp)
        for x in result:
            assert x in exp


def test_urljoin():
    for inp, expected in [
        (
            ["http://localhost:8090/api/publish", "debian"],
            "http://localhost:8090/api/publish/debian",
        ),
        (
            ["http://localhost:8090/api/publish/", "/debian"],
            "http://localhost:8090/api/publish/debian",
        ),
        (
            ["http://localhost:8090/api/publish/", "/debian/"],
            "http://localhost:8090/api/publish/debian/",
        ),
        (
            ["http://localhost:8090/api/publish", ":.", "stretch"],
            "http://localhost:8090/api/publish/:./stretch",
        ),
        (
            ["http://localhost:8090/api/publish", "s3:.", "stretch"],
            "http://localhost:8090/api/publish/s3:./stretch",
        ),
        (["/api", "publish"], "/api/publish"),
    ]:
        assert urljoin(*inp) == expected


def test_timedelta_pretty():
    for inp, expected in [
        (timedelta(microseconds=0), "0μs"),
        (timedelta(microseconds=0.1), "0μs"),
        (timedelta(microseconds=-0.1), "0μs"),
        (timedelta(microseconds=100), "100μs"),
        (timedelta(microseconds=-100), "-100μs"),
        (timedelta(microseconds=1000), "1ms"),
        (timedelta(microseconds=-1000), "-1ms"),
        (timedelta(seconds=5), "5s"),
        (timedelta(seconds=-5), "-5s"),
        (timedelta(minutes=1), "1m"),
        (timedelta(minutes=-1), "-1m"),
        (timedelta(seconds=65), "1m5s"),
        (timedelta(seconds=-65), "-1m5s"),
        (timedelta(minutes=65), "1h5m"),
        (timedelta(minutes=-65), "-1h5m"),
        (timedelta(minutes=65, seconds=10), "1h5m10s"),
        (timedelta(minutes=65, seconds=10, milliseconds=25), "1h5m10s25ms"),
        (
            timedelta(minutes=65, seconds=10, milliseconds=25, microseconds=100),
            "1h5m10s25ms100μs",
        ),
        (timedelta(days=1, hours=5), "1d5h"),
        (timedelta(weeks=2, hours=5), "14d5h"),
    ]:
        assert timedelta_pretty(inp) == expected
