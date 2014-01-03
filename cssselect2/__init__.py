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

from .parser import SelectorError
from .tree import ElementWrapper
from .compiler import compile_selector_list, CompiledSelector


VERSION = '0.1a0'


class Matcher(object):
    def __init__(self):
        self.id_selectors = {}
        self.class_selectors = {}
        self.local_name_selectors = {}
        self.namespace_selectors = {}
        self.other_selectors = []
        self.needs_sorting = []

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
        if selector.never_matches:
            return

        if selector.id is not None:
            selector_list = self.id_selectors.setdefault(selector.id, [])
        elif selector.class_name is not None:
            selector_list = self.class_selectors.setdefault(
                selector.class_name, [])
        elif selector.local_name is not None:
            selector_list = self.local_name_selectors.setdefault(
                selector.local_name, [])
        elif selector.namespace is not None:
            selector_list = self.namespace_selectors.setdefault(
                selector.namespace, [])
        else:
            selector_list = self.other_selectors

        self.needs_sorting.append(selector_list)
        selector_list.append((selector.test, selector.specificity, payload))


    def match(self, element):
        """
        Match selectors against the given element.

        :param element:
            An :class:`ElementWrapper`.
        :returns:
            An iterable of the :obj:`payload` objects associated
            to selectors that match element,
            in order of lowest to highest :attr:`~CompiledSelector.specificity`,
            and in order of addition with :meth:`add_selector`
            among selectors of equal specificity.

        """
        while self.needs_sorting:
            self.needs_sorting.pop().sort(key=operator.itemgetter(1))

        if element.id is not None:
            for test, _, payload in self.id_selectors.get(element.id, ()):
                if test(element):
                    yield payload
        for class_name in element.classes:
            for test, _, payload in self.class_selectors.get(class_name, ()):
                if test(element):
                    yield payload
        for test, _, payload in self.local_name_selectors.get(
                element.local_name, ()):
            if test(element):
                yield payload
        for test, _, payload in self.namespace_selectors.get(
                element.namespace_url, ()):
            if test(element):
                yield payload
        for test, _, payload in self.other_selectors:
            if test(element):
                yield payload
