# coding: utf8
"""
    cssselect2
    ----------

    CSS selectors for ElementTree.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from __future__ import unicode_literals

from .tree import ElementWrapper
from .compiler import compile_selector_list, CompiledSelector


VERSION = '0.1a0'


class Matcher(object):
    """
    :param payload:
        Any data associated to these selectors,
        such as :class:`declarations <~tinycss2.ast.Declaration>`
        parsed from the :attr:`~tinycss2.ast.QualifiedRule.content`
        of a style rule.
        Can be any Python object.
        It will be returned as-is by (TODO)
    """
    def __init__(self):
        self.selectors = []

    def add_compiled_selectors(self, selectors,
                               origin='author', important=False):
        ...

##    def match(self, element, style_attribute_data=None)
