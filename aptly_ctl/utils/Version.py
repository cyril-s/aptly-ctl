from functools import total_ordering
import logging
logger = logging.getLogger(__name__)
try:
    import apt
    system_ver_compare = True
except ImportError:
    system_ver_compare = False


@total_ordering
class Version:
    "Represents debian package version of the form [epoch:]upstream-version[-debian-revision]." \
        + " Throws ValueError if version format is incorrect."

    def __init__(self, version):

        self.upstream_version_allowed_chars = (".", "+", "~", "-", ":")
        self.revision_allowed_chars = (".", "+", "~")

        for i, c in enumerate(version):
            if ord(c) > 127:
                raise ValueError("Non-ASCII symbols in debian version is nonsense." \
                        + "Position {}, code porint '{:x}'.".format(i, ord(c)))

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
            raise ValueError("Version '{}'  has incorrect epoch '{}'.".format(version, epoch))

        if len(upstream_version) == 0 or not upstream_version[0].isdecimal():
            raise ValueError("Version '{}' contains incorrect upstream version '{}'.".format(version, upstream_version) \
                + " Upstream version is obligatory and must start with a digit.")

        for i, c in enumerate(upstream_version):
            if not c.isalnum() and c not in self.upstream_version_allowed_chars:
                raise ValueError("Upsream version '{}' of version '{}'".format(upstream_version, version) \
                    + " contains illegal character (position {}, code point {:X}).".format(i, ord(c)))

        if len(revision) == 0:
            raise ValueError("Debian revision '{}' of version '{}' is empty.".format(revision, version))

        for i, c in enumerate(revision):
            if not c.isalnum() and c not in self.revision_allowed_chars:
                raise ValueError("Debian revision '{}' of version '{}'".format(revision, version) \
                        + " contains illegal character (position {}, code point {:X}).".format(i, ord(c)))

        self.version = version
        self.epoch = int(epoch)
        self.upstream_version = upstream_version
        self.revision = revision


    def __repr__(self):
        return self.version

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __cmp__(self, other):
        if system_ver_compare:
            return apt.apt_pkg.version_compare(self.version, other.version)
        else:
            return self.version_compare(other)


    def _order(self, c):
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

    def _get_empty_str_on_index_error(self, arr, index):
        try:
            return arr[index]
        except IndexError:
            return ""

    def _compare_parts(self, a, b, decimal):
        if decimal:
            if a == "": a = "0"
            if b == "": b = "0"
            return int(a) - int(b)
        else:
            i = 0
            while i < (min(len(a), len(b)) + 1):
                res = self._order(self._get_empty_str_on_index_error(a, i)) \
                        - self._order(self._get_empty_str_on_index_error(b, i))
                if res != 0:
                    return res
                i += 1
            else:
                return 0

    def _get_part(self, s, decimal):
        "Strips first part of string containing either non-decimal or decimal characters." \
        + " Returns tuple (part, remider)."
        div = 0
        for c in s:
            if decimal and not c.isdecimal():
                break
            elif not decimal and c.isdecimal():
                break
            else:
                div += 1

        return (s[:div], s[div:])

    def version_compare(self, other):
        "Compares version of the form [epoch:]upstream-version[-debian-revision]" \
        + " according to Debian package version number format."

        # compare epoch
        diff = self.epoch - other.epoch
        if diff != 0:
            return diff

        # compare upstream version and debian revision
        for slf, othr in (self.upstream_version, other.upstream_version), (self.revision, other.revision):
            i = 0
            while len(slf) > 0 or len(othr) > 0:
                decimal = (i % 2 == 1) 
                slf_part, slf = self._get_part(slf, decimal=decimal)
                othr_part, othr = self._get_part(othr, decimal=decimal)
                diff = self._compare_parts(slf_part, othr_part, decimal=decimal)
                if diff != 0:
                    return diff
                i += 1

        # versions are equal
        return 0

