from functools import total_ordering
import logging
import re
from aptly_ctl.utils import Version

logger = logging.getLogger(__name__)

@total_ordering
class PackageRef:
    """
    Represents reference to package in Aptly repostitory.
    Can be built from such refs:
    aplty key: "[<prefix>]P<arch> <name> <version> <hash>",
    direct ref: "<name>_<arch>_<version>".
    Repo can in specified in reference: "<repo>/<reference>".
    In reference with version <repo> takes presendence on repo argument.
    """
    key_regexp = re.compile(r"(\w+?)?P(\w+) (\S+) (\S+) (\w+)$")
    dir_ref_regexp = re.compile(r"(\S+)_([a-zA-Z0-9.+-:~]+)_(\w+)$")

    def __init__(self, reference):
        self._fields = {}
        repo, sep, ref = reference.partition("/")
        if len(sep) == 0:
            ref = repo
            self.repo = None
        elif len(repo) == 0:
            self.repo = None
        else:
            self.repo = repo

        if self.key_regexp.match(ref):
            m = self.key_regexp.match(ref)
            self._fields["prefix"] = m.group(1) # None if empty
            self._fields["arch"] = m.group(2)
            self._fields["name"] = m.group(3)
            self._fields["version"] = Version(m.group(4))
            self._fields["hash"] = m.group(5)
        elif self.dir_ref_regexp.match(ref):
            m = self.dir_ref_regexp.match(ref)
            self._fields["prefix"] = None
            self._fields["name"] = m.group(1)
            self._fields["version"] = Version(m.group(2))
            self._fields["arch"] = m.group(3)
            self._fields["hash"] = None
        else:
            raise ValueError('Incorrect package reference "%s"' % reference)


    @property
    def prefix(self):
        return self._fields["prefix"]

    @property
    def arch(self):
        return self._fields["arch"]

    @property
    def name(self):
        return self._fields["name"]

    @property
    def version(self):
        return self._fields["version"]

    @property
    def hash(self):
        return self._fields["hash"]

    @hash.setter
    def hash(self, value):
        if self.hash is None:
            self._fields["hash"] = value
        else:
            raise AttributeError("Failed to overvrite existing hash {} with new {}".format(self.hash, value))

    @property
    def key(self):
        "Return either aptly key if hash is not empty or None if it is"
        if not self.hash:
            raise TypeError("Cannot build aptly key becuse hash is empty")
        p = self.prefix if self.prefix else ""
        return "{}P{} {} {} {}".format(p, self.arch, self.name, self.version, self.hash)

    @property
    def dir_ref(self):
        return "{}_{}_{}".format(self.name, self.version, self.arch)


    def __repr__(self):
        "Return the most accurate reference that is feedable to constructor"
        r = self.repo + "/" if self.repo else ""
        if self.hash:
            return r + self.key
        else:
            return r + self.dir_ref


    def __str__(self):
        "Return either key, or dir_ref if hash is empty"
        if self.hash:
            return self.key
        else:
            return self.dir_ref


    def __eq__(self, other):
        t_self = (
                self.name,
                self.prefix if self.prefix else "",
                self.arch,
                self.version,
                self.hash if self.hash else ""
                )
        t_other = (
                other.name,
                other.prefix if other.prefix else "",
                other.arch,
                other.version,
                other.hash if other.hash else ""
                )
        return t_self == t_other


    def __lt__(self, other):
        t_self = (
                self.name,
                self.prefix if self.prefix else "",
                self.arch,
                self.version,
                self.hash if self.hash else ""
                )
        t_other = (
                other.name,
                other.prefix if other.prefix else "",
                other.arch,
                other.version,
                other.hash if other.hash else ""
                )
        return t_self < t_other

