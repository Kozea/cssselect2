# coding: utf8
"""
    lselect
    -------

    CSS selectors for lxml.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from tinycss.tokenizer import tokenize_grouped

from . import parser


VERSION = '0.1a0'


def compile_string(string, namespaces=None):
    """Compile a list of selectors.

    :param string:
        The selectors, as a string. Can be either a single selector or a list
        of comma-separated selectors, as in CSS stylesheets.
    :param namespaces:
        A dictionary of all `namespace prefix declarations
        <http://www.w3.org/TR/selectors/#nsdecl>`_ in scope for this selector.
        Keys are namespace prefixes as strings, or ``None`` for the default
        namespace. Values are namespace URIs.
    :returns:
        An opaque object to be passed to :func:`match` or :func:`match_simple`.

    """
    if isinstance(string, bytes):
        string = string.decode('ascii')
    return compile_tokens(tokenize_grouped(string), namespaces)


def compile_tokens(tokens, namespaces=None):
    """Same as :func:`compile_string`, but the input is a list of tinycss
    "grouped" tokens rather than a string.

    """
    return [(selector, eval('lambda el: ' + _translate(selector.parsed_tree),
                            {}, {}))
            for selector in parser.parse(tokens, namespaces)]


def match(tree, selectors):
    """Match selectors against a document.

    :param tree:
        An lxml Element or ElementTree object.
    :param selectors:
        A list of ``(selector, data)`` tuples. ``selector`` is a result from
        :func:`compile_string` or :func:`compile_tokens`. ``data`` can be
        any object associated to the selector (such as a declaration block)
        and is returned in the results.
    :returns:
        A generator of ``(element, pseudo_element, specificity, data)``.
        The order of results is unspecified.

    """
    selectors = [(selector, test, data)
                 for selector_list, data in selectors
                 for selector, test in selector_list]
    for element in tree.iter():
        for selector, test, data in selectors:
            if test(element):
                yield (element, selector.pseudo_element,
                       selector.specificity, data)


def match_simple(tree, *selectors):
    """Match selectors against a document.

    :param tree:
        An lxml Element or ElementTree object.
    :param *selectors:
        Results from :func:`compile_string` or :func:`compile_tokens`.
    :returns:
        A set of elements.

    """
    results = match(tree, [(sel, None) for sel in selectors])
    return set(element for element, pseudo_element, _, _ in results
               if pseudo_element is None)


def _translate(selector):
    """Return a Python expression as a string."""
    if isinstance(selector, parser.CombinedSelector):
        left = _translate(selector.left)
        if left == '0':
            return left
        # No shortcut if left == '1', the element matching left needs to exist.

        if selector.combinator == ' ':
            left = 'any(%s for el in el.iterancestors())' % left
        elif selector.combinator == '>':
            # Empty list for False, non-empty list for True
            # Use list(generetor-expression) rather than [list-comprehension]
            # to create a new scope for the el variable.
            # List comprehensions do not create a scope in Python 2.x
            left = ('list(1 for el in [el.getparent()] '
                         'if el is not None and %s)' % left)
        elif selector.combinator == '+':
            left = ('list(1 for el in [el.getprevious()] '
                         'if el is not None and %s)' % left)
        elif selector.combinator == '~':
            left = 'any(%s for el in el.itersiblings(preceding=True))' % left
        else:
            raise ValueError('Unknown combinator', selector.combinator)

        right = _translate(selector.right)
        if right == '0':
            return right  # 0 and x == 0
        elif right == '1':
            return left  # 1 and x == x
        else:
            # Evaluate combinators right to left:
            return '%s and %s' % (right, left)

    elif isinstance(selector, parser.CompoundSelector):
        if len(selector.simple_selectors) == 1:
            return _translate(selector.simple_selectors[0])
        assert selector.simple_selectors
        return '(%s)' % ' and '.join(map(
            _translate, selector.simple_selectors))

    elif isinstance(selector, parser.ElementTypeSelector):
        ns = selector.namespace
        tag = selector.element_type
        if ns is any:
            return 'el.tag.rsplit("}", 1)[-1] == %r' % tag
        else:
            if ns is not None:
                tag = '{%s}%s' % (ns, tag)
            return 'el.tag == %r' % tag

    elif isinstance(selector, parser.UniversalSelector):
        ns = selector.namespace
        if ns is any:
            return '1'  # Like 'True', but without a global lookup
        elif ns is None:
            return 'el.tag[0] != "{"'
        else:
            return 'el.tag.startswith(%r)' % ('{%s}' % ns)

    elif isinstance(selector, parser.ClassSelector):
        assert selector.class_name  # syntax does not allow empty identifiers
        name = 'class'  # TODO: make this configurable.
        return _translate(parser.AttributeSelector(
            None, name, '~=', selector.class_name))

    elif isinstance(selector, parser.IDSelector):
        assert selector.ident  # syntax does not allow empty identifiers
        name = 'id'  # TODO: make this configurable.
        return _translate(parser.AttributeSelector(
            None, name, '=', selector.ident))

    elif isinstance(selector, parser.AttributeSelector):
        assert selector.namespace is None  # TODO handle namespaced attributes
        name = selector.name
        value = selector.value
        if selector.operator is None:
            return 'el.get(%r) is not None' % name
        elif selector.operator == '=':
            return 'el.get(%r) == %r' % (name, value)
        elif selector.operator == '~=':
            if len(value.split()) != 1 or value.strip() != value:
                # Optimization only, the else clause should have
                # the same behavior.
                return '0'  # Like 'False', but without a global lookup
            else:
                # TODO: only split on ASCII whitespace
                return '%r in el.get(%r, "").split()' % (value, name)
        elif selector.operator == '|=':
            # Empty list for False, non-empty list for True
            return ('[1 for value in [el.get(%r)] if value == %r or'
                    ' (value is not None and value.startswith(%r))]'
                    % (name, value, value + '-'))
        elif selector.operator == '^=':
            if value:
                return 'el.get(%r, "").startswith(%r)' % (name, value)
            else:
                return '0'  # Like 'False', but without a global lookup
        elif selector.operator == '$=':
            if value:
                return 'el.get(%r, "").endswith(%r)' % (name, value)
            else:
                return '0'
        elif selector.operator == '*=':
            if value:
                return '%r in el.get(%r, "")' % (value, name)
            else:
                return '0'
        else:
            raise ValueError('Unknown attribute operator', selector.operator)

    elif isinstance(selector, parser.PseudoClassSelector):
        if selector.name == 'link':
            # XXX HTML-only
            return _translate('a[href]')
        elif selector.name in ('visited', 'hover', 'active', 'focus',
                                'target'):
            return '0'  # Like 'False', but without a global lookup
        elif selector.name in ('enabled', 'disabled', 'checked'):
            # TODO
            return '0'  # Like 'False', but without a global lookup
        elif selector.name == 'root':
            return 'el.getparent() is None'
        elif selector.name == 'first-child':
            return 'el.getprevious() is None'
        elif selector.name == 'last-child':
            return 'el.getnext() is None'
        elif selector.name == 'first-of-type':
            return ('next(el.itersiblings(el.tag, preceding=True), None)'
                    ' is None')
        elif selector.name == 'last-of-type':
            return 'next(el.itersiblings(el.tag), None) is None'
        elif selector.name == 'only-child':
            return 'el.getprevious() is None and el.getnext() is None'
        elif selector.name == 'only-of-type':
            return ('next(el.itersiblings(el.tag, preceding=True), None)'
                    ' is None and '
                    'next(el.itersiblings(el.tag), None) is None')
        elif selector.name == 'empty':
            return 'next(el.iterchildren(), None) is None and (not el.text)'
        else:
            raise ValueError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, parser.FunctionalPseudoClassSelector):
        if selector.name == 'lang':
            lang = selector.parse_lang()
            name = 'lang'  # TODO: make this configurable.
            # TODO: matching should be case-insensitive
            lang = parser.AttributeSelector(None, name, '|=', lang)
            ancestor = parser.CombinedSelector(
                lang, ' ', parser.UniversalSelector(any))
            return '(%s or %s)' % (_translate(lang), _translate(ancestor))
        else:
            a, b = selector.parse_nth_child()
            # x is the number of siblings before/after the element
            # n is a positive or zero integer
            # x = a*n + b-1
            # x = a*n + B
            B = b - 1
            if a == 0:
                # x = B
                test = 'sum(1 for _ in %%s) == %i' % B
            else:
                # n = (x-B) / a
                # Empty list for False, non-empty list for True
                test = ('[1 for n, r in [divmod(sum(1 for _ in %%s) - %i, %i)]'
                        ' if r == 0 and n >= 0]' % (B, a))

            if selector.name == 'nth-child':
                return test % 'el.itersiblings(preceding=True)'
            elif selector.name == 'nth-last-child':
                return test % 'el.itersiblings()'
            elif selector.name == 'nth-of-type':
                return test % 'el.itersiblings(el.tag, preceding=True)'
            elif selector.name == 'nth-last-of-type':
                return test % 'el.itersiblings(el.tag)'
            else:
                raise ValueError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, parser.NegationSelector):
        test = _translate(selector.sub_selector)
        if test == '0':
            return '1'
        elif test == '1':
            return '0'
        else:
            return 'not ' + test

    else:
        raise TypeError(type(selector), selector)
