from functools import total_ordering
import logging
from typing import Any, Iterable, Callable, Dict, List, ClassVar, Tuple, TypeVar

try:
    import apt

    system_ver_compare = True
except ImportError:
    system_ver_compare = False

logger = logging.getLogger(__name__)

StrOrInt = TypeVar("StrOrInt", str, int)


def rotate(
    key_fmt: str, sort_func: Callable[[Any], Any], n: int, seq: Iterable,
) -> List[Any]:
    """
    Returns items in seq to rotate according to configured policy.
    seq is divided in groups by a hash key which is derived from
    key_fmt. Then items in every group are sorted by key set by
    sort_func in ascending order and last abs(n) items are selected.
    If n >= 0 the rest of items are returned for a group.
    If n < 0 these items are returned for a group.
    key_fmt is a python format string. Each item is passed to it as 'o' attribute.
    """
    h = {}  # type: Dict[str, List[Any]]
    for item in seq:
        h.setdefault(key_fmt.format(o=item), []).append(item)
    for k, v in h.items():
        v.sort(key=sort_func)
        N = min(len(v), abs(n))
        h[k] = v[: len(v) - N] if n >= 0 else v[len(v) - N :]
    return list(sum(h.values(), []))


@total_ordering
class DebianVersion:
    """
    Represents debian package version of the form
    [epoch:]upstream-version[-debian-revision].
    Throws ValueError if version format is incorrect.
    """

    upstream_version_allowed_chars: ClassVar[Tuple[str, ...]] = (
        ".",
        "+",
        "~",
        "-",
        ":",
    )
    revision_allowed_chars: ClassVar[Tuple[str, ...]] = (".", "+", "~")

    version: str
    epoch: int
    upstream_version: str
    revision: str

    def __init__(self, version: str) -> None:
        for i, c in enumerate(version):
            if ord(c) > 127:
                raise ValueError(
                    "Non-ASCII symbols in debian version is nonsense."
                    + "Position {}, code porint '{:x}'.".format(i, ord(c))
                )

        # strip epoch
        epoch, sep, upstream_version_revision = version.partition(":")

        # special case: no epoch means 0 epoch
        if len(upstream_version_revision) == 0 and len(sep) == 0:
            upstream_version_revision = epoch
            epoch = "0"

        # strip debian revision
        upstream_version, sep, revision = upstream_version_revision.rpartition("-")

        # special case: no debian revision need to be treated like "-0"
        # empty revision in something like "1.1-" will be handled in syntax check
        if len(upstream_version) == 0 and len(sep) == 0:
            upstream_version = revision
            revision = "0"

        # check syntax
        if not epoch.isdecimal():
            raise ValueError(
                "Version '{}'  has incorrect epoch '{}'.".format(version, epoch)
            )

        if len(upstream_version) == 0 or not upstream_version[0].isdecimal():
            raise ValueError(
                "Version '{}' contains incorrect upstream version '{}'.".format(
                    version, upstream_version
                )
                + " Upstream version is obligatory and must start with a digit."
            )

        for i, c in enumerate(upstream_version):
            if not c.isalnum() and c not in self.upstream_version_allowed_chars:
                raise ValueError(
                    "Upsream version '{}' of version '{}'".format(
                        upstream_version, version
                    )
                    + " contains illegal character (position {}, code point {:X}).".format(
                        i, ord(c)
                    )
                )

        if len(revision) == 0:
            raise ValueError(
                "Debian revision '{}' of version '{}' is empty.".format(
                    revision, version
                )
            )

        for i, c in enumerate(revision):
            if not c.isalnum() and c not in self.revision_allowed_chars:
                raise ValueError(
                    "Debian revision '{}' of version '{}'".format(revision, version)
                    + " contains illegal character (position {}, code point {:X}).".format(
                        i, ord(c)
                    )
                )

        self.version = version
        self.epoch = int(epoch)
        self.upstream_version = upstream_version
        self.revision = revision

    def __repr__(self) -> str:
        return "".join(map(str, self._hashable_tuple))

    def __str__(self) -> str:
        return self.version

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DebianVersion):
            raise NotImplemented
        return self.__cmp__(other) == 0

    def __lt__(self, other: "DebianVersion") -> bool:
        return self.__cmp__(other) < 0

    def __cmp__(self, other: "DebianVersion") -> int:
        if system_ver_compare:
            return apt.apt_pkg.version_compare(self.version, other.version)
        else:
            return self.version_compare(other)

    @property
    def _hashable_tuple(self) -> Tuple[object, ...]:
        parts = [self.epoch, ":"]
        for c, s in enumerate([self.upstream_version, "-", self.revision]):
            i = 0
            while len(s) > 0:
                decimal = i % 2 == 1
                part, s = self._get_part(s, decimal)
                parts.append(part)
                i += 1
            else:
                if c != 1 and not decimal:
                    parts.append("0")
        return tuple(parts)

    def __hash__(self) -> int:
        return hash(self._hashable_tuple)

    def _order(self, c: str) -> int:
        if c.isdecimal():
            return 0
        elif c.isalpha():
            return ord(c)
        elif c == "~":
            return -1
        elif c:
            return ord(c) + 256
        else:
            return 0

    def _get_empty_str_on_index_error(self, arr: List[str], index: int) -> str:
        try:
            return arr[index]
        except IndexError:
            return ""

    def _compare_parts(self, a: StrOrInt, b: StrOrInt, decimal: bool) -> int:
        if decimal:
            return int(a) - int(b)
        i = 0
        while i < (min(len(a), len(b)) + 1):
            res = self._order(self._get_empty_str_on_index_error(a, i)) - self._order(
                self._get_empty_str_on_index_error(b, i)
            )
            if res != 0:
                return res
            i += 1
        else:
            return 0

    def _get_part(self, s: str, decimal: bool) -> Tuple[str, str]:
        """
        Strips first part of string containing either non-decimal or decimal characters.
        Returns tuple (part, remider).
        """
        div = 0
        for c in s:
            if decimal and not c.isdecimal():
                break
            elif not decimal and c.isdecimal():
                break
            else:
                div += 1

        if decimal and div == 0:
            return ("0", s[:])
        else:
            return (s[:div], s[div:])

    def version_compare(self, other: "DebianVersion") -> int:
        """
        Compares version of the form [epoch:]upstream-version[-debian-revision]
        according to Debian package version number format.
        """

        # compare epoch
        diff = self.epoch - other.epoch
        if diff != 0:
            return diff

        # compare upstream version and debian revision
        for slf, othr in (
            (self.upstream_version, other.upstream_version),
            (self.revision, other.revision),
        ):
            i = 0
            while len(slf) > 0 or len(othr) > 0:
                decimal = i % 2 == 1
                slf_part, slf = self._get_part(slf, decimal=decimal)
                othr_part, othr = self._get_part(othr, decimal=decimal)
                diff = self._compare_parts(slf_part, othr_part, decimal=decimal)
                if diff != 0:
                    return diff
                i += 1

        # versions are equal
        return 0
