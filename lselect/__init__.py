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


class _State(object):
    """Keeps track of identifiers in the generated Python code."""
    def __init__(self):
        self.element_id = 0

    def identifier(self):
        return 'el_%s' % self.element_id

    def next_identifier(self):
        self.element_id += 1


def compile_selector(selector):
    """Return a (element -> bool) callable."""
    state = _State()
    element = state.identifier()
    expr = translate(selector, state)
    return eval('lambda %s: %s' % (element, expr), {}, {})


def translate(selector, state):
    """Return a Python expression as a string."""
    element = state.identifier()

    if isinstance(selector, bytes):
        selector = selector.decode('ascii')
        # fall through to unicode

    if isinstance(selector, unicode):
        expressions = [expr
                       for sel in cssselect.parse(selector)
                       for expr in [translate(sel.parsed_tree, state)]
                       # 0 or x == x
                       if expr != '0']
        if not expressions:
            return '0'  # any([]) == False
        elif '1' in expressions:
            return '1'  # 1 or x == 1
        else:
            return ' or '.join(expressions)

    elif isinstance(selector, cssselect.parser.Element):
        ns = selector.namespace
        tag = selector.element
        if ns and tag:
            tag = '{%s}%s' % (ns, tag)
            return '(%s.tag == %r)' % (element, tag)
        elif ns:
            ns = '{%s}' % ns
            return '(%s.tag.startswith(%r))' % (element, tag)
        elif tag:
            return '(%s.tag.rsplit("}", 1)[-1] == %r)' % (element, tag)
        else:
            return '1'  # Like 'True', but without a global lookup

    elif isinstance(selector, cssselect.parser.CombinedSelector):
        right = translate(selector.subselector, state)
        if right == '0':
            return right
        state.next_identifier()
        next_element = state.identifier()
        left = translate(selector.selector, state)
        if left == '0':
            return left
        # No shortcut if left == '1', the element matching left needs to exist.

        if selector.combinator == ' ':
            left = 'any(%s for %s in %s.iterancestors())' % (
                left, next_element, element)
        elif selector.combinator == '>':
            left = (
                # Empty list for False, non-empty list for True
                '[1 for %s in [%s.getparent()] if %s is not None and %s]'
                % (next_element, element, next_element, left))
        elif selector.combinator == '+':
            left = (
                # Empty list for False, non-empty list for True
                '[1 for %s in [%s.getprevious()] if %s is not None and %s]'
                % (next_element, element, next_element, left))
        elif selector.combinator == '~':
            left = 'any(%s for %s in %s.itersiblings(preceding=True))' % (
                left, next_element, element)
        else:
            raise ValueError('Unknown combinator', selector.combinator)

        if right == '1':
            return left
        else:
            # Evaluate combinators right to left:
            return '%s and %s' % (right, left)

    elif isinstance(selector, cssselect.parser.Class):
        assert selector.class_name  # syntax does not allow empty identifiers
        name = 'class'  # TODO: make this configurable.
        selector = cssselect.parser.Attrib(
            selector.selector, None, name, '~=', selector.class_name)
        return translate(selector, state)

    elif isinstance(selector, cssselect.parser.Hash):
        assert selector.id  # syntax does not allow empty identifiers
        name = 'id'  # TODO: make this configurable.
        selector = cssselect.parser.Attrib(
            selector.selector, None, name, '=', selector.id)
        return translate(selector, state)

    # This is common to all remaining types of selector:
    rest = translate(selector.selector, state)
    if rest == '0':
        return rest
    elif rest == '1':
        rest = ''
    else:
        rest = ' and ' + rest

    if isinstance(selector, cssselect.parser.Attrib):
        assert selector.namespace is None  # TODO handle namespaced attributes
        name = selector.attrib
        value = selector.value
        if selector.operator == 'exists':
            expr = '%s.get(%r) is not None' % (element, name)
        elif selector.operator == '=':
            expr = '%s.get(%r) == %r' % (element, name, value)
        elif selector.operator == '~=':
            if len(value.split()) != 1 or value.strip() != value:
                # Optimization only, the else clause should have
                # the same behavior.
                expr = '0'  # Like 'False', but without a global lookup
            else:
                # TODO: only split on ASCII whitespace
                expr = '%r in %s.get(%r, "").split()' % (value, element, name)
        elif selector.operator == '|=':
            # Empty list for False, non-empty list for True
            expr = ('[1 for value in [%s.get(%r)] if value == %r or'
                    ' (value is not None and value.startswith(%r))]'
                    % (element, name, value, value + '-'))
        elif selector.operator == '^=':
            if value:
                expr = '%s.get(%r, "").startswith(%r)' % (
                    element, name, value)
            else:
                expr = '0'  # Like 'False', but without a global lookup
        elif selector.operator == '$=':
            if value:
                expr = '%s.get(%r, "").endswith(%r)' % (
                    element, name, value)
            else:
                expr = '0'  # Like 'False', but without a global lookup
        elif selector.operator == '*=':
            if value:
                expr = '%r in %s.get(%r, "")' % (
                    value, element, name)
            else:
                expr = '0'  # Like 'False', but without a global lookup
        else:
            raise ValueError('Unknown attribute operator', selector.operator)

    elif isinstance(selector, cssselect.parser.Pseudo):
        if selector.ident == 'link':
            # XXX HTML-only
            expr = translate('a[href]', state)
        elif selector.ident in ('visited', 'hover', 'active', 'focus',
                                'target'):
            expr = '0'  # Like 'False', but without a global lookup
        elif selector.ident in ('enabled', 'disabled', 'checked'):
            # TODO
            expr = '0'  # Like 'False', but without a global lookup
        elif selector.ident == 'root':
            expr = element + '.getparent() is None'
        elif selector.ident == 'first-child':
            expr = element + '.getprevious() is None'
        elif selector.ident == 'last-child':
            expr = element + '.getnext() is None'
        elif selector.ident == 'first-of-type':
            expr = ('next(%s.itersiblings(%s.tag, preceding=True), None)'
                    ' is None' % (element, element))
        elif selector.ident == 'last-of-type':
            expr = 'next(%s.itersiblings(%s.tag), None) is None' % (
                element, element)
        elif selector.ident == 'only-child':
            expr = '%s.getprevious() is None and %s.getnext() is None' % (
                element, element)
        elif selector.ident == 'only-of-type':
            expr = ('next(%s.itersiblings(%s.tag, preceding=True), None)'
                    ' is None and '
                    'next(%s.itersiblings(%s.tag), None) is None'
                    % (element, element, element, element))
        elif selector.ident == 'empty':
            expr = ('next(%s.iterchildren(), None) is None and (not %s.text)'
                    % (element, element))
        else:
            raise ValueError('Unknown pseudo-class', selector.ident)


    elif isinstance(selector, cssselect.parser.Function):
        if selector.name == 'lang':
            if selector.argument_types() not in (['STRING'], ['IDENT']):
                raise TypeError(selector.arguments)
            # TODO
            expr = '0'  # Like 'False', but without a global lookup

        a, b = cssselect.parser.parse_series(selector.arguments)  # may raise
        # x is the number of siblings before/after the element
        # n is a positive or zero integer
        # x = a*n + b-1
        # x = a*n + B
        B = b - 1
        if a == 0:
            # x = B
            test = 'sum(1 for _ in %%s) == %s' % B
        else:
            # n = (x-B) / a
            # Empty list for False, non-empty list for True
            test = ('[1 for n, r in [divmod(sum(1 for _ in %%s) - %s, %s)]'
                    ' if r == 0 and n >= 0]' % (B, a))

        if selector.name == 'nth-child':
            expr = test % '%s.itersiblings(preceding=True)' % element
        elif selector.name == 'nth-last-child':
            expr = test % '%s.itersiblings()' % element
        elif selector.name == 'nth-of-type':
            expr = test % '%s.itersiblings(%s.tag, preceding=True)' % (
                element, element)
        elif selector.name == 'nth-last-of-type':
            expr = test % '%s.itersiblings(%s.tag)' % (element, element)
        else:
            raise ValueError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, cssselect.parser.Negation):
        test = translate(selector.subselector, state)
        if test == '0':
            expr = '1'
        elif test == '1':
            expr = '0'
        else:
            expr = 'not ' + test

    else:
        raise TypeError(type(selector), selector)

    return '(%s%s)' % (expr, rest)
