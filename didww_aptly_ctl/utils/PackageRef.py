from functools import total_ordering
import logging
import re
from didww_aptly_ctl.utils import Version

logger = logging.getLogger(__name__)

@total_ordering
class PackageRef:
    """
    Represents reference to package in Aptly repostitory.
    Can be built from such refs:
    aplty key: "[<prefix>]P<arch> <name> <version>[ <hash>]",
    direct ref: "<name>_<arch>_<version>".
    Repo can in specified in reference: "<repo>/<reference>".
    In reference with version <repo> takes presendence on repo argument.
    """
    key_regexp = re.compile(r"(\w+?)?P(\w+) (\S+) (\S+)( \w+)?$")
    dir_ref_regexp = re.compile(r"(\S+)_([a-zA-Z0-9.+-:~]+)_(\w+)$")

    def __init__(self, reference, local_repo=None):
        repo, sep, ref = reference.partition("/")
        if len(sep) == 0:
            ref = repo
            self.repo = local_repo
        elif len(repo) > 0:
            self.repo = repo
        else:
            self.repo = local_repo

        if self.key_regexp.match(ref):
            m = self.key_regexp.match(ref)
            self.prefix = "" if m.group(1) is None else m.group(1)
            self.arch = m.group(2)
            self.name = m.group(3)
            self.version = Version(m.group(4))
            self.hash = "" if m.group(5) is None else m.group(5)[1:] # strip leading space
        elif self.dir_ref_regexp.match(ref):
            m = self.dir_ref_regexp.match(ref)
            self.prefix = ""
            self.name = m.group(1)
            self.version = Version(m.group(2))
            self.arch = m.group(3)
            self.hash = ""
        else:
            raise ValueError('Incorrect package reference "%s"' % reference)


    @property
    def key(self):
        h = " " + self.hash if self.hash else ""
        return "{}P{} {} {}{}".format(self.prefix, self.arch, self.name, self.version, h)


    @property
    def dir_ref(self):
        return "{}_{}_{}".format(self.name, self.arch, self.version)


    def __repr__(self):
        r = self.repo + "/" if self.repo else ""
        return r + self.key


    def __str__(self):
        return self.key


    def __eq__(self, other):
        t_self = (self.name, self.prefix, self.arch, self.version, self.hash)
        t_other = (other.name, other.prefix, other.arch, other.version, other.hash)
        return t_self == t_other


    def __lt__(self, other):
        t_self = (self.name, self.prefix, self.arch, self.version, self.hash)
        t_other = (other.name, other.prefix, other.arch, other.version, other.hash)
        return t_self < t_other


