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
from aptly_ctl.util import DebianVersion as Version


logger = logging.getLogger(__name__)
KEY_REGEXP = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
DIR_REF_REGEXP = re.compile(r"(\S+?)_(\S+?)_(\w+)")


def read_control_file_lines(package_path: str) -> str:
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
                with tar_file.extractfile("./control") as control_file:
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
