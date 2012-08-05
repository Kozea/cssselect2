# coding: utf8
"""
    lselect.tests
    -------------

    Test suite for lselect

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from . import VERSION


def test_version():
    """Dummy test to show that the import works."""
    assert VERSION.startswith('0')
