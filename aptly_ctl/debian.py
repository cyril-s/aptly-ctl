from functools import total_ordering
import logging
import tarfile
import unix_ar  # type: ignore
from typing import (
    ClassVar,
    Dict,
    Iterator,
    List,
    Tuple,
    TypeVar,
)


log = logging.getLogger(__name__)


def read_control_file_lines(package_path: str) -> Iterator[str]:
    """Yields lines of control file from debian package"""
    with open(package_path, "rb") as package_file:
        ar_archive = unix_ar.open(package_file)
        for ar_member_info in ar_archive.infolist():
            ar_member_filename = ar_member_info.name.decode("utf-8", errors="replace")
            if ar_member_filename.startswith("control.tar"):
                break
        else:
            raise ValueError("Failed to find control archive inside debian package")
        with ar_archive.open(ar_member_filename) as ar_member_file:
            with tarfile.open(fileobj=ar_member_file) as tar_file:
                # allow raising no method __enter__ __exit__ when ./control is directory
                # and extractfile return None
                with tar_file.extractfile("./control") as control_file:  # type: ignore
                    for line in control_file:
                        yield line.decode("utf-8", errors="replace").rstrip()


def get_control_file_fields(package_file: str) -> Dict[str, str]:
    """Returns dictionay of control file fields from debian package"""
    fields = {}  # type: Dict[str, str]
    last_field = ""
    line_num = 0
    for line in read_control_file_lines(package_file):
        if not line:
            if len(fields) == 0:
                continue
            break
        if line[0].isspace():
            # control file lines from read_control_file_lines are stripped.
            # Add newline to the first line of multiline field
            if not fields[last_field].endswith("\n"):
                # https://github.com/aptly-dev/aptly/blob/37166af321bc30031f5abd7e85ea473fa807d98f/deb/format.go#L291
                # aptly does not strip leading space from the first line of multiline fields
                fields[last_field] = " " + fields[last_field] + "\n"
            fields[last_field] += line + "\n"
        else:
            last_field, _, value = line.partition(":")
            if not last_field or not value.strip():
                raise ValueError(
                    "Malformed control file: {}: {}".format(line_num, line)
                )
            fields[last_field] = value.strip()
        line_num += 1
    return fields


StrOrInt = TypeVar("StrOrInt", str, int)


@total_ordering
class Version:
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
        if not isinstance(other, Version):
            raise NotImplementedError
        return self.__cmp__(other) == 0

    def __lt__(self, other: "Version") -> bool:
        return self.__cmp__(other) < 0

    def __cmp__(self, other: "Version") -> int:
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
        while i < (min(len(a), len(b)) + 1):  # type: ignore
            res = self._order(self._get_empty_str_on_index_error(a, i)) - self._order(  # type: ignore
                self._get_empty_str_on_index_error(b, i)  # type: ignore
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

    def version_compare(self, other: "Version") -> int:
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
