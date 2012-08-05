# coding: utf8
"""
    lselect.tests
    -------------

    Test suite for lselect

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from . import parse


def test_foo():
    """Dummy test to show that the import works
    and running half the code does not crash.

    """
    assert parse('* a > b|* + c|d ~ .e#f[g][g=h][g~=h][g|=h]:link'
                 ':not(:nth-last-of-type(3n-5))')
