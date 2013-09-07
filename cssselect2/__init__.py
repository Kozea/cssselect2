# coding: utf8
"""
    cssselect2
    ----------

    CSS selectors for ElementTree.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from tinycss2 import parse_component_value_list

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
    return compile_component_values(
        parse_component_value_list(string), namespaces)


def compile_component_values(tokens, namespaces=None):
    """Same as :func:`compile_string`, but the input is a list of tinycss2
    component values rather than a string.

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
    """Return a boolean expression, as a Python source string.

    When evaluated in a context where the `el` variable is an lxml element,
    tells whether the element is a subject of `selector`.

    """
    # To avoid precedence-related bugs, any sub-expression that is passed
    # around must be "atomic": add parentheses when the top-level would be
    # an operator. Bare literals and function calls are fine.

    # 1 and 0 are used for True and False to avoid global lookups.

    if isinstance(selector, parser.CombinedSelector):
        left_inside = _translate(selector.left)
        if left_inside == '0':
            return '0'  # 0 and x == 0
        elif left_inside == '1':
            # 1 and x == x, but the element matching 1 still needs to exist.
            if selector.combinator in (' ', '>'):
                left = '(el.getparent() is not None)'
            elif selector.combinator in ('~', '+'):
                left = '(el.getprevious() is not None)'
            else:
                raise ValueError('Unknown combinator', selector.combinator)
        # Rebind the `el` name inside a generator-expressions (in a new scope)
        # so that 'left_inside' applies to different elements.
        elif selector.combinator == ' ':
            left = 'any(%s for el in el.iterancestors())' % left_inside
        elif selector.combinator == '>':
            # Empty list for False, non-empty list for True
            # Use list(generator-expression) rather than [list-comprehension]
            # to create a new scope for the el variable.
            # List comprehensions do not create a scope in Python 2.x
            left = ('list(1 for el in [el.getparent()] '
                         'if el is not None and %s)' % left_inside)
        elif selector.combinator == '+':
            left = ('list(1 for el in [el.getprevious()] '
                         'if el is not None and %s)' % left_inside)
        elif selector.combinator == '~':
            left = ('any(%s for el in el.itersiblings(preceding=1))'
                    % left_inside)
        else:
            raise ValueError('Unknown combinator', selector.combinator)

        right = _translate(selector.right)
        if right == '0':
            return '0'  # 0 and x == 0
        elif right == '1':
            return left  # 1 and x == x
        else:
            # Evaluate combinators right to left:
            return '(%s and %s)' % (right, left)

    elif isinstance(selector, parser.CompoundSelector):
        sub_expressions = [
            expr for expr in map(_translate, selector.simple_selectors)
            if expr != '1']
        if len(sub_expressions) == 1:
            return sub_expressions[0]
        elif '0' in sub_expressions:
            return '0'
        elif sub_expressions:
            return '(%s)' % ' and '.join(sub_expressions)
        else:
            return '1'  # all([]) == True

    elif isinstance(selector, parser.ElementTypeSelector):
        ns = selector.namespace
        local_name = selector.element_type
        # In lxml, Element.tag is a string with the format '{ns}local_name'
        # or just 'local_name' for the empty namespace.
        if ns is None:
            return '(el.tag.rsplit("}", 1)[-1] == %r)' % local_name
        else:
            tag = local_name if ns != '' else '{%s}%s' % (ns, local_name)
            return '(el.tag == %r)' % tag

    elif isinstance(selector, parser.UniversalSelector):
        ns = selector.namespace
        if ns is None:
            return '1'
        elif ns == '':
            return '(el.tag[0] != "{")'
        else:
            return 'el.tag.startswith(%r)' % ('{%s}' % ns)

    elif isinstance(selector, parser.ClassSelector):
        assert selector.class_name  # syntax does not allow empty identifiers
        name = 'class'  # TODO: make this configurable.
        return _translate(parser.AttributeSelector(
            '', name, '~=', selector.class_name))

    elif isinstance(selector, parser.IDSelector):
        assert selector.ident  # syntax does not allow empty identifiers
        name = 'id'  # TODO: make this configurable.
        return _translate(parser.AttributeSelector(
            '', name, '=', selector.ident))

    elif isinstance(selector, parser.AttributeSelector):
        assert selector.namespace == ''  # TODO handle namespaced attributes
        name = selector.name
        value = selector.value
        if selector.operator is None:
            return '(el.get(%r) is not None)' % name
        elif selector.operator == '=':
            return '(el.get(%r) == %r)' % (name, value)
        elif selector.operator == '~=':
            if len(value.split()) != 1 or value.strip() != value:
                return '0'
            else:
                # TODO: only split on ASCII whitespace
                return '(%r in el.get(%r, "").split())' % (value, name)
        elif selector.operator == '|=':
            # Empty list for False, non-empty list for True
            return ('[1 for value in [el.get(%r)] if value == %r or'
                    ' (value is not None and value.startswith(%r))]'
                    % (name, value, value + '-'))
        elif selector.operator == '^=':
            if value:
                return 'el.get(%r, "").startswith(%r)' % (name, value)
            else:
                return '0'
        elif selector.operator == '$=':
            if value:
                return 'el.get(%r, "").endswith(%r)' % (name, value)
            else:
                return '0'
        elif selector.operator == '*=':
            if value:
                return '(%r in el.get(%r, ""))' % (value, name)
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
            # Not applicable in a static context: never match.
            return '0'
        elif selector.name in ('enabled', 'disabled', 'checked'):
            # TODO
            return '0'
        elif selector.name == 'root':
            return '(el.getparent() is None)'
        elif selector.name == 'first-child':
            return '(el.getprevious() is None)'
        elif selector.name == 'last-child':
            return '(el.getnext() is None)'
        elif selector.name == 'first-of-type':
            return ('(next(el.itersiblings(el.tag, preceding=1), None)'
                    ' is None)')
        elif selector.name == 'last-of-type':
            return '(next(el.itersiblings(el.tag), None) is None)'
        elif selector.name == 'only-child':
            return '(el.getprevious() is None and el.getnext() is None)'
        elif selector.name == 'only-of-type':
            return ('(next(el.itersiblings(el.tag, preceding=1), None)'
                    ' is None and '
                    'next(el.itersiblings(el.tag), None) is None)')
        elif selector.name == 'empty':
            return '(next(el.iterchildren(), None) is None and not el.text)'
        else:
            raise ValueError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, parser.FunctionalPseudoClassSelector):
        if selector.name == 'lang':
            lang = selector.parse_lang()
            name = 'lang'  # TODO: make this configurable.
            # TODO: matching should be case-insensitive
            lang = parser.AttributeSelector('', name, '|=', lang)
            ancestor = parser.CombinedSelector(
                lang, ' ', parser.UniversalSelector(None))
            return '(%s or %s)' % (_translate(lang), _translate(ancestor))
        else:
            a, b = selector.parse_nth_child()
            # x is the number of siblings before/after the element
            # Matches if a positive or zero integer n exists so that:
            # x = a*n + b-1
            # x = a*n + B
            B = b - 1
            if a == 0:
                # x = B
                test = '(sum(1 for _ in %%s) == %i)' % B
            else:
                # n = (x - B) / a
                # Empty list for False, non-empty list for True
                test = ('[1 for n, r in [divmod(sum(1 for _ in %%s) - %i, %i)]'
                        ' if r == 0 and n >= 0]' % (B, a))

            if selector.name == 'nth-child':
                return test % 'el.itersiblings(preceding=1)'
            elif selector.name == 'nth-last-child':
                return test % 'el.itersiblings()'
            elif selector.name == 'nth-of-type':
                return test % 'el.itersiblings(el.tag, preceding=1)'
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
            return '(not %s)' % test

    else:
        raise TypeError(type(selector), selector)
