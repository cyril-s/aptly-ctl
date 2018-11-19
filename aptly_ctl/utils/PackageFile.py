import logging
import hashlib
from os.path import basename, abspath, realpath
from fnvhash import fnv1a_64

logger = logging.getLogger(__name__)

class PackageFile:

    read_buffer_size = 1024 * 1024

    def __init__(self, filepath):
        hashes = [ hashlib.md5(), hashlib.sha1(), hashlib.sha256() ]
        self.size = 0
        with open(filepath, 'rb', self.read_buffer_size) as f:
            while True:
                b = f.read(self.read_buffer_size)
                if len(b) == 0: break
                self.size += len(b)
                for h in hashes:
                    h.update(b)
        self.md5 = hashes[0].hexdigest()
        self.sha1 = hashes[1].hexdigest()
        self.sha256 = hashes[2].hexdigest()
        self.path = filepath
        self.abspath = abspath(self.path)
        self.realpath = realpath(self.abspath)
        self.filename = basename(self.realpath)

    @property
    def ahash(self):
        data = b''
        data += bytes(self.filename, "ascii")
        data += self.size.to_bytes(8, 'big')
        data += bytes(self.md5, "ascii")
        data += bytes(self.sha1, "ascii")
        data += bytes(self.sha256, "ascii")
        digest = fnv1a_64(data)
        return digest

    def __str__(self):
        return "name={self.filename} abs={self.abspath} size={self.size} hash={self.ahash:x}".format(self=self)

    def pretty(self):
        return str(self) + "\n\tMD5\t{self.md5}\n\tSHA1\t{self.sha1}\n\tSHA256\t{self.sha256}".format(self=self)

if __name__ == "__main__":
    import sys
    p = PackageFile(sys.argv[1])
    print(p.pretty())
