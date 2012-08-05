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


def compile_selector(selector):
    """Return a (element -> bool) callable."""
    return eval('lambda el: ' + translate(selector), {}, {})


def translate(selector):
    """Return a Python expression as a string."""
    if isinstance(selector, bytes):
        selector = selector.decode('ascii')
        # fall through to unicode

    if isinstance(selector, unicode):
        expressions = [expr
                       for sel in cssselect.parse(selector)
                       for expr in [translate(sel.parsed_tree)]
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
            return 'el.tag == %r' % tag
        elif ns:
            ns = '{%s}' % ns
            return 'el.tag.startswith(%r)' % tag
        elif tag:
            return 'el.tag.rsplit("}", 1)[-1] == %r' % tag
        else:
            return '1'  # Like 'True', but without a global lookup

    elif isinstance(selector, cssselect.parser.CombinedSelector):
        left = translate(selector.selector)
        if left == '0':
            return left
        # No shortcut if left == '1', the element matching left needs to exist.

        if selector.combinator == ' ':
            left = 'any(%s for el in el.iterancestors())' % left
        elif selector.combinator == '>':
            # Empty list for False, non-empty list for True
            left = ('[1 for el in [el.getparent()] if el is not None and %s]'
                    % left)
        elif selector.combinator == '+':
            left = ('[1 for el in [el.getprevious()] if el is not None and %s]'
                    % left)
        elif selector.combinator == '~':
            left = 'any(%s for el in el.itersiblings(preceding=True))' % left
        else:
            raise ValueError('Unknown combinator', selector.combinator)

        right = translate(selector.subselector)
        if right == '0':
            return right  # 0 and x == 0
        elif right == '1':
            return left  # 1 and x == x
        else:
            # Evaluate combinators right to left:
            return '%s and %s' % (right, left)

    elif isinstance(selector, cssselect.parser.Class):
        assert selector.class_name  # syntax does not allow empty identifiers
        name = 'class'  # TODO: make this configurable.
        return translate(cssselect.parser.Attrib(
            selector.selector, None, name, '~=', selector.class_name))

    elif isinstance(selector, cssselect.parser.Hash):
        assert selector.id  # syntax does not allow empty identifiers
        name = 'id'  # TODO: make this configurable.
        return translate(cssselect.parser.Attrib(
            selector.selector, None, name, '=', selector.id))

    # This is common to all remaining types of selector:
    rest = translate(selector.selector)
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
            expr = 'el.get(%r) is not None' % name
        elif selector.operator == '=':
            expr = 'el.get(%r) == %r' % (name, value)
        elif selector.operator == '~=':
            if len(value.split()) != 1 or value.strip() != value:
                # Optimization only, the else clause should have
                # the same behavior.
                expr = '0'  # Like 'False', but without a global lookup
            else:
                # TODO: only split on ASCII whitespace
                expr = '%r in el.get(%r, "").split()' % (value, name)
        elif selector.operator == '|=':
            # Empty list for False, non-empty list for True
            expr = ('[1 for value in [el.get(%r)] if value == %r or'
                    ' (value is not None and value.startswith(%r))]'
                    % (name, value, value + '-'))
        elif selector.operator == '^=':
            if value:
                expr = 'el.get(%r, "").startswith(%r)' % (name, value)
            else:
                expr = '0'  # Like 'False', but without a global lookup
        elif selector.operator == '$=':
            if value:
                expr = 'el.get(%r, "").endswith(%r)' % (name, value)
            else:
                expr = '0'
        elif selector.operator == '*=':
            if value:
                expr = '%r in el.get(%r, "")' % (value, name)
            else:
                expr = '0'
        else:
            raise ValueError('Unknown attribute operator', selector.operator)

    elif isinstance(selector, cssselect.parser.Pseudo):
        if selector.ident == 'link':
            # XXX HTML-only
            expr = translate('a[href]')
        elif selector.ident in ('visited', 'hover', 'active', 'focus',
                                'target'):
            expr = '0'  # Like 'False', but without a global lookup
        elif selector.ident in ('enabled', 'disabled', 'checked'):
            # TODO
            expr = '0'  # Like 'False', but without a global lookup
        elif selector.ident == 'root':
            expr = 'el.getparent() is None'
        elif selector.ident == 'first-child':
            expr = 'el.getprevious() is None'
        elif selector.ident == 'last-child':
            expr = 'el.getnext() is None'
        elif selector.ident == 'first-of-type':
            expr = ('next(el.itersiblings(el.tag, preceding=True), None)'
                    ' is None')
        elif selector.ident == 'last-of-type':
            expr = 'next(el.itersiblings(el.tag), None) is None'
        elif selector.ident == 'only-child':
            expr = 'el.getprevious() is None and el.getnext() is None'
        elif selector.ident == 'only-of-type':
            expr = ('next(el.itersiblings(el.tag, preceding=True), None)'
                    ' is None and '
                    'next(el.itersiblings(el.tag), None) is None')
        elif selector.ident == 'empty':
            expr = 'next(el.iterchildren(), None) is None and (not el.text)'
        else:
            raise ValueError('Unknown pseudo-class', selector.ident)


    elif isinstance(selector, cssselect.parser.Function):
        if selector.name == 'lang':
            if selector.argument_types() not in (['STRING'], ['IDENT']):
                raise TypeError(selector.arguments)
            name = 'lang'  # TODO: make this configurable.
            universal = cssselect.parser.Element()
            lang = selector.arguments[0].value
            # TODO: matching should be case-insensitive
            lang = cssselect.parser.Attrib(universal, None, name, '|=', lang)
            ancestor = cssselect.parser.CombinedSelector(lang, ' ', universal)
            expr = '(%s or %s)' % (translate(lang), translate(ancestor))
        else:
            # May raise:
            a, b = cssselect.parser.parse_series(selector.arguments)
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
                expr = test % 'el.itersiblings(preceding=True)'
            elif selector.name == 'nth-last-child':
                expr = test % 'el.itersiblings()'
            elif selector.name == 'nth-of-type':
                expr = test % 'el.itersiblings(el.tag, preceding=True)'
            elif selector.name == 'nth-last-of-type':
                expr = test % 'el.itersiblings(el.tag)'
            else:
                raise ValueError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, cssselect.parser.Negation):
        test = translate(selector.subselector)
        if test == '0':
            expr = '1'
        elif test == '1':
            expr = '0'
        else:
            expr = 'not ' + test

    else:
        raise TypeError(type(selector), selector)

    return '(%s%s)' % (expr, rest)
