# coding: utf8
"""
    lselect
    -------

    CSS selectors for lxml.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

import cssselect
import cssselect.parser


VERSION = '0.1a0'


try:
    unicode
except NameError:
    unicode = str  # Python 3


def parse(selector):
    def dashmatch(name, value, sub):
        def test(el):
            attr = el.get(name)
            return (
                attr == value or
                (attr is not None and attr.startswith(value + '-'))
            ) and sub(el)
        return test

    def includes(name, value, sub):
        if len(value.split()) != 1 or value.strip() != value:
            # Optimization only, the else clause should have the same behavior.
            return lambda el: False
        else:
            # TODO: do not split on non-ASCII whitespace
            return lambda el: value in el.get(name, '').split() and sub(el)


    if isinstance(selector, unicode):
        selector, = cssselect.parse(selector)
        return parse(selector.parsed_tree)

    elif isinstance(selector, cssselect.parser.Element):
        ns = selector.namespace
        tag = selector.element
        if ns and tag:
            tag = '{%s}%s' % (ns, tag)
            return lambda el: el.tag == tag
        elif ns:
            ns = '{%s}' % ns
            return lambda el: el.tag.startswith(ns)
        elif tag:
            return lambda el: el.tag.rsplit('}', 1)[-1] == tag
        else:
            return lambda el: True

    elif isinstance(selector, cssselect.parser.Attrib):
        assert selector.namespace is None  # TODO handle namespaced attributes
        name = selector.attrib
        value = selector.value
        sub = parse(selector.selector)
        if selector.operator == 'exists':
            return lambda el: el.get(name) is not None and sub(el)
        elif selector.operator == '=':
            return lambda el: el.get(name) == value and sub(el)
        elif selector.operator == '~=':
            return includes(name, value, sub)
        elif selector.operator == '|=':
            return dashmatch(name, value, sub)
        elif selector.operator == '^=':
            if value:
                return lambda el: el.get(name, '').startswith(value) and sub(el)
            else:
                return lambda el: False
        elif selector.operator == '$=':
            if value:
                return lambda el: el.get(name, '').endswith(value) and sub(el)
            else:
                return lambda el: False
        elif selector.operator == '*=':
            if value:
                return lambda el: value in el.get(name, '') and sub(el)
            else:
                return lambda el: False
        else:
            raise ValueError('Unknown attribute operator', selector.operator)

    elif isinstance(selector, cssselect.parser.Class):
        assert selector.class_name  # syntax does not allow empty identifiers
        name = 'class'  # TODO: make this configurable.
        return includes(name, selector.class_name, parse(selector.selector))

    elif isinstance(selector, cssselect.parser.Hash):
        assert selector.id  # syntax does not allow empty identifiers
        name = 'id'  # TODO: make this configurable.
        return includes(name, selector.id, parse(selector.selector))

    elif isinstance(selector, cssselect.parser.Pseudo):
        sub = parse(selector.selector)
        if selector.ident == 'link':
            # XXX HTML-only
            return lambda el: (el.tag == 'a' and el.get('href') is not None
                               and sub(el))
        elif selector.ident in ('visited', 'hover', 'active', 'focus',
                                'target'):
            return lambda el: False
        elif selector.ident in ('enabled', 'disabled', 'checked'):
            # TODO
            return lambda el: False
        elif selector.ident == 'root':
            return lambda el: el.getparent() is None and sub(el)
        elif selector.ident == 'fist-child':
            return lambda el: el.getprevious() is None and sub(el)
        elif selector.ident == 'last-child':
            return lambda el: el.getnext() is None and sub(el)
        elif selector.ident == 'fist-of-type':
            return lambda el: (
                next( el.itersiblings(el.tag, preceding=True), None) is None
                and sub(el))
        elif selector.ident == 'last-of-type':
            return lambda el: next(
                el.itersiblings(el.tag), None) is None and sub(el)
        elif selector.ident == 'only-child':
            return lambda el: (el.getprevious() is None
                               and el.getnext() is None
                               and sub(el))
        elif selector.ident == 'only-of-type':
            return lambda el: (
                next(el.itersiblings(el.tag, preceding=True), None) is None
                and next(el.itersiblings(el.tag), None) is None
                and sub(el))
        elif selector.ident == 'empty':
            return lambda el: next(el.iterchidren(), None) is None and sub(el)


    elif isinstance(selector, cssselect.parser.Function):
        sub = parse(selector.selector)
        if selector.name == 'lang':
            if selector.argument_types() not in (['STRING'], ['IDENT']):
                raise TypeError(selector.arguments)
            # TODO
            return lambda el: False

        a, b = cssselect.parser.parse_series(selector.arguments)  # may raise
        # We test for a*n + b-1 siblings before or after the element:
        b -= 1
        if selector.name == 'nth-child':
            return lambda el: sum(1 for _ in
                el.itersiblings(preceding=True)) % a == b and sub(el)
        elif selector.name == 'nth-last-child':
            return lambda el: sum(1 for _ in
                el.itersiblings()) % a == b and sub(el)
        elif selector.name == 'nth-of-type':
            return lambda el: sum(1 for _ in
                el.itersiblings(el.tag, preceding=True)) % a == b and sub(el)
        elif selector.name == 'nth-last-of-type':
            return lambda el: sum(1 for _ in
                el.itersiblings(el.tag)) % a == b and sub(el)

    elif isinstance(selector, cssselect.parser.Negation):
        sub = parse(selector.selector)
        test = parse(selector.subselector)
        return lambda el: (not test(el)) and sub(el)

    elif isinstance(selector, cssselect.parser.CombinedSelector):
        left = parse(selector.selector)
        right = parse(selector.subselector)
        if selector.combinator == ' ':
            return lambda el: left(el) and any(
                right(ancestor) for ancestor in right.iterancestors())
        elif selector.combinator == '>':
            def child_test(el):
                if not left(el):
                    return False
                parent = el.getparent()
                return parent is not None and right(parent)
            return child_test
        elif selector.combinator == '+':
            def sibling_test(el):
                if not left(el):
                    return False
                previous = el.getprevious()
                return previous is not None and right(previous)
            return sibling_test
        elif selector.combinator == '~':
            return lambda el: left(el) and any(
                right(sibl) for sibl in right.itersiblings(preceding=True))
        else:
            raise ValueError('Unknown combinator', selector.combinator)
    else:
        raise TypeError(selector)
