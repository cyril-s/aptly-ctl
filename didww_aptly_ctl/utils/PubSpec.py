class PubSpec:

    def __init__(self, distribution, prefix="."):
        if '/' in distribution:
            pref, sep, dist = distribution.rpartition('/')
            if len(pref) == 0 or len(dist) == 0:
                raise ValueError("refspec invalid")
            self._prefix = pref
            self._distribution = dist
        else:
            self._prefix = prefix
            self._distribution = distribution

    @property
    def prefix(self):
        return self._prefix

    @property
    def distribution(self):
        return self._distribution

    def __repr__(self):
        return self.prefix + "/" + self.distribution

    def __str__(self):
        return self.__repr__()
