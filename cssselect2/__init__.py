# coding: utf8
"""
    cssselect2
    ----------

    CSS selectors for ElementTree.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from __future__ import unicode_literals

import operator

from .tree import ElementWrapper
from .compiler import compile_selector_list, CompiledSelector


VERSION = '0.1a0'


class Matcher(object):
    def __init__(self):
        self.selectors = []
        self.is_sorted = True

    def add_selector(self, selector, payload):
        """

        :param selector:
            A :class:`CompiledSelector` object.
        :param payload:
            Some data associated to the selector,
            such as :class:`declarations <~tinycss2.ast.Declaration>`
            parsed from the :attr:`~tinycss2.ast.QualifiedRule.content`
            of a style rule.
            It can be any Python object,
            and will be returned as-is by :meth:`match`.

        """
        self.is_sorted = False
        self.selectors.append((selector.test, selector.specificity, payload))


    def match(self, element):
        """
        Match selectors against the given element.

        :param element:
            An :class:`ElementWrapper`.
        :returns:
            An iterable of the :obj:`payload` objects associated
            to selectors that match element,
            in order of highest to lowest :attr:`~CompiledSelector.specificity`.

        """
        if not self.is_sorted:
            self.selectors.sort(key=operator.itemgetter(1), reverse=True)
            self.is_sorted = True
        for test, _, payload in self.selectors:
            if test(element):
                yield payload
