from . context import didww_aptly_ctl
from didww_aptly_ctl.utils import AptlyKey
import pytest
import random

class TestAptlyKey(object):
    # Test comparison
    def test_cmp_equlity(self):
        A = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A == B

    def test_cmp_name(self):
        A = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = AptlyKey("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A > B and B < A

    def test_cmp_architecture(self):
        A = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = AptlyKey("Pi386 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        assert A < B and B > A

    def test_cmp_version(self):
        A = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = AptlyKey("Pamd64 didww-billing 2.2.0~rc6 f2b7dc2061b9d95c")
        assert A < B and B > A

    def test_cmp_hash(self):
        A = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c")
        B = AptlyKey("Pamd64 didww-billing 2.2.0~rc5 x2b7dc2061b9d95c")
        assert A < B and B > A

    def test_sort_order(self):
        ordered_list = [
                AptlyKey("Pamd64 aptly 2.2.0~rc5 f2b7dc2061b9d95c"),
                AptlyKey("Pi386 aptly 2.2.0~rc6 f2b7dc2061b9d95c"),
                AptlyKey("Pamd64 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c"),
                AptlyKey("Pamd64 didww-billing 2.2.0~rc5 x2b7dc2061b9d95c"),
                AptlyKey("Pamd64 didww-billing 2.2.0~rc6 f2b7dc2061b9d95c"),
                AptlyKey("Pi386 didww-billing 2.2.0~rc5 f2b7dc2061b9d95c"),
                ]
        shuffled_list = ordered_list[:]
        random.shuffle(shuffled_list)
        shuffled_list.sort()
        assert ordered_list == shuffled_list

