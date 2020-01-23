import logging
import re
from collections import OrderedDict
import typing
import hashlib
import os.path
import fnvhash
import aptly_api
from aptly_ctl.util import DebianVersion as Version
import datetime
import aptly_ctl.exceptions


logger = logging.getLogger(__name__)
KEY_REGEXP = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
DIR_REF_REGEXP = re.compile(r"(\S+?)_(\S+?)_(\w+)")


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
        # Trying to guess future aptly key
        # FIXME get info from package itself and not it's filename
        parsed_dir_ref = DIR_REF_REGEXP.match(fileinfo.filename)
        if not parsed_dir_ref:
            raise aptly_ctl.exceptions.AptlyCtlError(
                "Failed to guess aptly key for filename " + fileinfo.filename
            )
        name, _, arch = parsed_dir_ref.groups()
        version = Version(parsed_dir_ref.group(2))
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
