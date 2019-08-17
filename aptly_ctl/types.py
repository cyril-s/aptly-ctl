import logging
import re
from collections import namedtuple
import hashlib
import os.path
import fnvhash
from aptly_ctl.util import DebianVersion as Version


logger = logging.getLogger(__name__)
key_regexp = re.compile(r"(\w*?)P(\w+) (\S+) (\S+) (\w+)$")
dir_ref_regexp = re.compile(r"(\S+?)_(\S+?)_(\w+)")


PackageFileInfo = namedtuple("PackageFileInfo",
        ["filename", "path", "origpath", "size", "md5", "sha1", "sha256"])


class Package(namedtuple("Package",
        ["name", "version", "arch", "prefix", "files_hash", "fields", "file"],
        defaults=[None, None])):
    """Represents package in aptly or on filesystem"""
    __slots__ = ()

    @property
    def key(self):
        return "{o.prefix}P{o.arch} {o.name} {o.version} {o.files_hash}".format(o=self)

    @property
    def dir_ref(self):
        return "{o.name}_{o.version}_{o.arch}".format(o=self)

    @classmethod
    def fromAptlyApi(cls, p):
        """Create from instance of aply_api.Package"""
        kwargs = {}
        try:
            parsed_key = key_regexp.match(p.key).groups()
        except (AttributeError, TypeError) as e:
            raise ValueError("Invalid package: {}".format(p)) from e

        kwargs["prefix"], kwargs["arch"], kwargs["name"] = parsed_key[:3]
        kwargs["version"] = Version(parsed_key[3])
        kwargs["files_hash"] = parsed_key[4]
        if p.fields:
            kwargs["fields"] = tuple(sorted(p.fields.items()))

        return cls(**kwargs)

    @classmethod
    def fromFile(cls, filepath):
        hashes = [ hashlib.md5(), hashlib.sha1(), hashlib.sha256() ]
        size = 0
        buff_size = 1024 * 1024
        with open(filepath, 'rb', buff_size) as f:
            while True:
                b = f.read(buff_size)
                if len(b) == 0: break
                size += len(b)
                for h in hashes:
                    h.update(b)
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
            name, version, arch = dir_ref_regexp.match(fileinfo.filename).groups()
        except AttributeError:
            logger.warning("Failed to guess aptly key for filename %s", fileinfo.filename)
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
    Represents local repo in aptly
    """
    __slots__ = ()

    @classmethod
    def fromAptlyApi(cls, repo, packages=None):
        return cls(**repo._asdict(), packages=packages)
