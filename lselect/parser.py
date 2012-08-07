# coding: utf8
"""
    lselect.parser
    --------------

    A parser for CSS selectors, based on the tinycss tokenizer.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from tinycss.tokenizer import tokenize_grouped


def parse_string(string, namespaces=None):
    if isinstance(string, bytes):
        string = string.decode('ascii')
    return parse(tokenize_grouped(string), namespace)


def parse(tokens, namespaces=None):
    namespaces = namespaces or {}
    raise NotImplementedError


def ascii_lower(string):
    """Lower-case, but only in the ASCII range."""
    return string.encode('utf8').lower().decode('utf8')


class Selector(object):
    def __init__(self, tree, pseudo_element=None):
        self.parsed_tree = tree
        if pseudo_element is None:
            self.pseudo_element = pseudo_element
            #: Tuple of 3 integers: http://www.w3.org/TR/selectors/#specificity
            self.specificity = tree.specificity
        else:
            self.pseudo_element = ascii_lower(pseudo_element)
            a, b, c = tree.specificity
            self.specificity = a, b, c + 1



class CombinedSelector(object):
    def __init__(self, left, combinator, right):
        #: Compound or simple selector
        self.left = left
        # One of `` `` (a single space), ``>``, ``+`` or ``~``.
        self.combinator = combinator
        #: Simple selector
        self.right = right

    @property
    def specificity(self):
        a1, b1, c1 = self.left.specificity
        a2, b2, c2 = self.right.specificity
        return a1 + a2, b1 + b2, c1 + c2


class CompoundSelector(object):
    """Aka. sequence of simple selectors, in Level 3."""
    def __init__(self, simple_selectors):
        self.simple_selectors = simple_selectors

    @property
    def specificity(self):
        # zip(*foo) turns [(a1, b1, c1), (a2, b2, c2), ...]
        # into [(a1, a2, ...), (b1, b2, ...), (c1, c2, ...)]
        return tuple(map(sum, zip(*
            (sel.specificity for sel in self.simple_selectors))))


def ElementTypeSelector(object):
    specificity =  0, 0, 1

    def __init__(self, namespace, element_type):
        #: Either ``None`` for no namespace, the built-in function
        #: ``any`` (used as a marker) for any namespace (``*`` in CSS)
        #: or a namespace name/URI (not a prefix) as a string.
        #:
        #: Note that simple type selectors like ``E`` are resolved to
        #: ``NS|E`` if there is a default namespace ``*|E`` otherwise.
        self.namespace = namespace
        self.element_type = element_type


def UniversalSelector(object):
    specificity =  0, 0, 0

    def __init__(self, namespace):
        #: Same as :attr:`ElementTypeSelector.namespace`
        self.namespace = namespace


class IDSelector(object):
    specificity =  1, 0, 0

    def __init__(self, ident):
        self.ident = ident


class ClassSelector(object):
    specificity =  0, 1, 0

    def __init__(self, class_name):
        self.class_name = class_name


class AttributeSelector(object):
    specificity =  0, 1, 0

    def __init__(self, name, operator, value):
        self.name = name
        #: A string like ``=`` or ``~=``, or None for ``[attr]`` selectors
        self.operator = operator
        #: A string, or None for ``[attr]`` selectors
        self.value = value


class PseudoClassSelector(object):
    specificity =  0, 1, 0

    def __init__(self, name):
        self.name = name


class FunctionalPseudoClassSelector(object):
    specificity =  0, 1, 0

    def __init__(self, name, arguments):
        self.name = name
        #: A tinycss :class:`TokenList`
        self.arguments = arguments


class NegationSelector(object):
    def __init__(self, sub_selector):
        self.sub_selector = sub_selector

    @property
    def specificity(self):
        return self.sub_selector.specificity
