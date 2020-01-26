from functools import total_ordering
import logging
import re
from collections import OrderedDict
import typing
import hashlib
import os.path
import datetime
import tarfile
import unix_ar
import fnvhash
import aptly_api


logger = logging.getLogger(__name__)
KEY_REGEXP = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
DIR_REF_REGEXP = re.compile(r"(\S+?)_(\S+?)_(\w+)")


def read_control_file_lines(package_path: str) -> typing.Iterator[str]:
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


def get_control_file_fields(package_file: str) -> typing.Dict[str, str]:
    """Returns dictionay of control file fields from debian package"""
    fields = {}  # type: typing.Dict[str, str]
    last_field = ""
    line_num = 0
    for line in read_control_file_lines(package_file):
        if not line:
            if len(fields) == 0:
                continue
            break
        if line[0].isspace():
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


StrOrInt = typing.TypeVar("StrOrInt", str, int)


@total_ordering
class Version:
    """
    Represents debian package version of the form
    [epoch:]upstream-version[-debian-revision].
    Throws ValueError if version format is incorrect.
    """

    upstream_version_allowed_chars: typing.ClassVar[typing.Tuple[str, ...]] = (
        ".",
        "+",
        "~",
        "-",
        ":",
    )
    revision_allowed_chars: typing.ClassVar[typing.Tuple[str, ...]] = (".", "+", "~")

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
    def _hashable_tuple(self) -> typing.Tuple[object, ...]:
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

    def _get_empty_str_on_index_error(self, arr: typing.List[str], index: int) -> str:
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

    def _get_part(self, s: str, decimal: bool) -> typing.Tuple[str, str]:
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


class PackageFileInfo(typing.NamedTuple):
    filename: str
    path: str
    origpath: str
    size: int
    md5: str
    sha1: str
    sha256: str


class Package(typing.NamedTuple):
    """Represents package in aptly or on local filesystem"""

    name: str
    version: Version
    arch: str
    prefix: str
    files_hash: str
    fields: typing.Optional[typing.Dict[str, str]] = None
    file: typing.Optional[PackageFileInfo] = None

    @property
    def key(self) -> str:
        """Returns aptly key"""
        return "{o.prefix}P{o.arch} {o.name} {o.version} {o.files_hash}".format(o=self)

    @property
    def dir_ref(self) -> str:
        """Returns aptly dir ref"""
        return "{o.name}_{o.version}_{o.arch}".format(o=self)

    @classmethod
    def from_aptly_api(cls, package: aptly_api.Package) -> "Package":
        """Create from instance of aptly_api.Package"""
        parsed_key = KEY_REGEXP.match(package.key)
        if parsed_key is None:
            raise ValueError("Invalid package: {}".format(package))
        prefix, arch, name, _, files_hash = parsed_key.groups()
        version = Version(parsed_key.group(4))
        fields = None
        if package.fields:
            fields = OrderedDict(sorted(package.fields.items()))
        return cls(
            name=name,
            version=version,
            arch=arch,
            prefix=prefix,
            files_hash=files_hash,
            fields=fields,
        )

    @classmethod
    def from_key(cls, key: str) -> "Package":
        """Create from instance of aptly key"""
        return cls.from_aptly_api(aptly_api.Package(key, None, None, None))

    @classmethod
    def from_file(cls, filepath: str) -> "Package":
        """
        Build representation of aptly package from package on local filesystem
        """
        hashes = [hashlib.md5(), hashlib.sha1(), hashlib.sha256()]
        size = 0
        buff_size = 1024 * 1024
        with open(filepath, "rb", buff_size) as file:
            while True:
                chunk = file.read(buff_size)
                if not chunk:
                    break
                size += len(chunk)
                for _hash in hashes:
                    _hash.update(chunk)
        fields = get_control_file_fields(filepath)
        name = fields["Package"]
        version = Version(fields["Version"])
        arch = fields["Architecture"]
        fileinfo = PackageFileInfo(
            md5=hashes[0].hexdigest(),
            sha1=hashes[1].hexdigest(),
            sha256=hashes[2].hexdigest(),
            size=size,
            filename=os.path.basename(os.path.realpath(filepath)),
            path=os.path.realpath(os.path.abspath(filepath)),
            origpath=filepath,
        )
        data = b"".join(
            [
                bytes(fileinfo.filename, "ascii"),
                fileinfo.size.to_bytes(8, "big"),
                bytes(fileinfo.md5, "ascii"),
                bytes(fileinfo.sha1, "ascii"),
                bytes(fileinfo.sha256, "ascii"),
            ]
        )
        files_hash = "{:x}".format(fnvhash.fnv1a_64(data))
        return cls(
            name=name,
            version=version,
            arch=arch,
            prefix="",
            files_hash=files_hash,
            fields=None,
            file=fileinfo,
        )


class Repo(typing.NamedTuple):
    """Represents local repo in aptly"""

    name: str
    comment: typing.Optional[str] = None
    default_distribution: typing.Optional[str] = None
    default_component: typing.Optional[str] = None
    packages: typing.FrozenSet[Package] = frozenset()

    @classmethod
    def from_aptly_api(
        cls, repo: aptly_api.Repo, packages: typing.FrozenSet[Package] = frozenset()
    ) -> "Repo":
        """Create from instance of aply_api.Repo"""
        return cls(
            name=repo.name,
            comment=repo.comment,
            default_distribution=repo.default_distribution,
            default_component=repo.default_component,
            packages=packages,
        )


class Snapshot(typing.NamedTuple):
    """Represents snapshot in aptly"""

    name: str
    description: typing.Optional[str] = None
    created_at: typing.Optional[datetime.datetime] = None
    packages: typing.FrozenSet[Package] = frozenset()

    @classmethod
    def from_aptly_api(
        cls,
        snapshot: aptly_api.Snapshot,
        packages: typing.FrozenSet[Package] = frozenset(),
    ) -> "Snapshot":
        """Create from instance of aply_api.Snapshot"""
        return cls(
            name=snapshot.name,
            description=snapshot.description,
            created_at=snapshot.created_at,
            packages=packages,
        )


PackageContainer = typing.TypeVar("PackageContainer", Repo, Snapshot)
PackageContainers = typing.Union[Repo, Snapshot]
