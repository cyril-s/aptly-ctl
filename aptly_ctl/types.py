import logging
import re
from collections import namedtuple
import hashlib
import os.path
import fnvhash
import aptly_api
from aptly_ctl.util import DebianVersion as Version


logger = logging.getLogger(__name__)
KEY_REGEXP = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
DIR_REF_REGEXP = re.compile(r"(\S+?)_(\S+?)_(\w+)")


PackageFileInfo = namedtuple(
    "PackageFileInfo",
    ["filename", "path", "origpath", "size", "md5", "sha1", "sha256"]
    )


class Package(namedtuple(
        "Package",
        ["name", "version", "arch", "prefix", "files_hash", "fields", "file"],
        defaults=[None, None]
        )):
    """Represents package in aptly or on local filesystem"""
    __slots__ = ()

    @property
    def key(self):
        """Returns aptly key"""
        return "{o.prefix}P{o.arch} {o.name} {o.version} {o.files_hash}".format(o=self)

    @property
    def dir_ref(self):
        """Returns aptly dir ref"""
        return "{o.name}_{o.version}_{o.arch}".format(o=self)

    @classmethod
    def from_aptly_api(cls, package):
        """Create from instance of aptly_api.Package"""
        try:
            parsed_key = KEY_REGEXP.match(package.key).groups()
        except (AttributeError, TypeError) as exc:
            raise ValueError("Invalid package: {}".format(package)) from exc
        kwargs = {}
        kwargs["prefix"], kwargs["arch"], kwargs["name"] = parsed_key[:3]
        kwargs["version"] = Version(parsed_key[3])
        kwargs["files_hash"] = parsed_key[4]
        if package.fields:
            kwargs["fields"] = tuple(sorted(package.fields.items()))
        return cls(**kwargs)

    @classmethod
    def from_key(cls, key):
        """Create from instance of aptly key"""
        return cls.from_aptly_api(aptly_api.Package(key, None, None, None))

    @classmethod
    def from_file(cls, filepath):
        """
        Build representation of aptly package from package on local filesystem
        """
        hashes = [hashlib.md5(), hashlib.sha1(), hashlib.sha256()]
        size = 0
        buff_size = 1024 * 1024
        with open(filepath, 'rb', buff_size) as file:
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
        data = b''.join([
            bytes(fileinfo.filename, "ascii"),
            fileinfo.size.to_bytes(8, 'big'),
            bytes(fileinfo.md5, "ascii"),
            bytes(fileinfo.sha1, "ascii"),
            bytes(fileinfo.sha256, "ascii"),
            ])
        files_hash = fnvhash.fnv1a_64(data)
        # Trying to guess future aptly key
        # FIXME get info from package itself and not it's filename
        try:
            name, version, arch = DIR_REF_REGEXP.match(fileinfo.filename).groups()
        except AttributeError:
            logger.warning("Failed to guess aptly key for filename %s",
                           fileinfo.filename)
            name, version, arch = None, None, None
        else:
            version = Version(version)

        return cls(
            name=name,
            version=version,
            arch=arch,
            prefix="",
            files_hash=files_hash,
            fields=None,
            file=fileinfo
            )


class Repo(namedtuple(
        "Repo",
        ["name", "comment", "default_distribution", "default_component", "packages"],
        defaults=[None, None, None, None]
        )):
    """
    Represents local repo in aptly with optional field packages which is best
    used when contains frozenset of Package instances
    """
    __slots__ = ()

    @classmethod
    def from_aptly_api(cls, repo, packages=None):
        """Create from instance of aply_api.Repo"""
        return cls(**repo._asdict(), packages=packages)


class Snapshot(namedtuple(
        "Snapshot",
        ["name", "description", "created_at", "packages"],
        defaults=[None, None, None]
        )):
    """
    Represents snapshot in aptly with optional field packages which is best
    used when contains frozenset of Package instances
    """
    __slots__ = ()

    @classmethod
    def from_aptly_api(cls, snapshot, packages=None):
        """Create from instance of aply_api.Snapshot"""
        return cls(**snapshot._asdict(), packages=packages)
