from functools import total_ordering
import logging
import re
from didww_aptly_ctl.utils import Version
from didww_aptly_ctl.exceptions import DidwwAptlyCtlError

logger = logging.getLogger(__name__)

@total_ordering
class AptlyKey:
    "Class to represent atply key e.g. 'Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c'"

    key_regexp = re.compile(r"P(\w+) (\S+) (\S+) (\w+)$")
    dir_ref_regexp = re.compile(r"([\w-]+)_([\w~.-]+)_(\w+)$")

    @staticmethod
    def fromDirRef(client, repo, dir_ref):
        """
        Searches repo for package specified by direct referece and returns its key.
        Returns None if cannot find. Raises DdidwwAptlyCtlError if obtaines multiple results.
        Uses aptly-api-client client.
        """
        if not AptlyKey.dir_ref_regexp.match(dir_ref):
            raise ValueError('Incorrect direct reference "%s"' % dir_ref)
    
        search_result = client.repos.search_packages(repo, dir_ref)
        if len(search_result) == 0:
            key = None
        elif len(search_result) == 1:
            key = search_result[0][0]
        else:
            keys = [ k[0] for k in search_result ]
            raise DidwwAptlyCtlError(
                "Search by direct reference {} returned many results: {}".format(dir_ref, keys), logger=logger)
    
        return AptlyKey(key, repo)


    def __init__(self, key, repo=None):
        m = AptlyKey.key_regexp.match(key)
        if not m or len(m.groups()) != 4:
            raise ValueError('Incorrect aptly key "%s"' % key)

        self.key = key
        self.arch = m.group(1)
        self.name = m.group(2)
        self.version = Version(m.group(3))
        self.package_hash = m.group(4)
        if repo is not None:
            self.repo = repo


    def getDirRef(self):
        """
        Converts aptly key to direct reference 
        ("didww-billing_2.2.0~rc5_amd64").
        """
        return "_".join([self.name, str(self.version), self.arch])

    def __repr__(self):
        return self.key


    def __str__(self):
        return self.__repr__()


    def __eq__(self, other):
        t_self = (self.name, self.arch, self.version, self.package_hash)
        t_other = (other.name, other.arch, other.version, other.package_hash)
        return t_self == t_other


    def __lt__(self, other):
        t_self = (self.name, self.arch, self.version, self.package_hash)
        t_other = (other.name, other.arch, other.version, other.package_hash)
        return t_self < t_other

    def exists(self, client):
        if not hasattr(self, "repo"):
            raise ValueError("Method works only when 'repo' attribute is present")
        return AptlyKey.fromDirRef(client, self.repo, self.getDirRef()) is not None

    def repo_exists(self, client):
        if not hasattr(self, repo):
            raise ValueError("Method works only when 'repo' attribute is present")
        try:
            return client.repo.show(self.repo) is not None
        except AptlyAPIException as e:
            if e.status_code == 404:
                return False
            else:
                raise
