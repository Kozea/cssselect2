from __future__ import unicode_literals

import re

from tinycss2.nth import parse_nth

from . import parser


# http://dev.w3.org/csswg/selectors/#whitespace
split_whitespace = re.compile('[^ \t\r\n\f]+').findall


def compile_selector_list(input, namespaces=None):
    """Compile a (comma-separated) list of selectors.

    :param input:
        A :term:`tinycss2:string`,
        or an iterable of tinycss2 :term:`tinycss2:component values`
        such as the :attr:`~tinycss2.ast.QualifiedRule.predule` of a style rule.
    :param namespaces:
        A optional dictionary of all `namespace prefix declarations
        <http://www.w3.org/TR/selectors/#nsdecl>`_ in scope for this selector.
        Keys are namespace prefixes as strings, or ``None`` for the default
        namespace.
        Values are namespace URLs as strings.
        If omitted, assume that no prefix is declared.
    :returns:
        A list of opaque :class:`CompiledSelector` objects.

    """
    return [
        CompiledSelector(
            eval(
                'lambda el: ' + _compile_node(selector.parsed_tree),
                {'split_whitespace': split_whitespace},
                {},
            ),
            selector.specificity,
            selector.pseudo_element,
        )
        for selector in parser.parse(input, namespaces)
    ]


class CompiledSelector(object):
    def __init__(self, test, specificity, pseudo_element):
        self.test = test
        self.specificity = specificity
        self.pseudo_element = pseudo_element


def _compile_node(selector):
    """Return a boolean expression, as a Python source string.

    When evaluated in a context where the `el` variable is an
    :class:`~cssselect2.tree.Element` object,
    tells whether the element is a subject of `selector`.

    """
    # To avoid precedence-related bugs, any sub-expression that is passed
    # around must be "atomic": add parentheses when the top-level would be
    # an operator. Bare literals and function calls are fine.

    # 1 and 0 are used for True and False to avoid global lookups.

    if isinstance(selector, parser.CombinedSelector):
        left_inside = _compile_node(selector.left)
        if left_inside == '0':
            return '0'  # 0 and x == 0
        elif left_inside == '1':
            # 1 and x == x, but the element matching 1 still needs to exist.
            if selector.combinator in (' ', '>'):
                left = '(el.parent is not None)'
            elif selector.combinator in ('~', '+'):
                left = '(el.previous is not None)'
            else:
                raise ValueError('Unknown combinator', selector.combinator)
        # Rebind the `el` name inside a generator-expressions (in a new scope)
        # so that 'left_inside' applies to different elements.
        elif selector.combinator == ' ':
            left = 'any(%s for el in el.iter_ancestors())' % left_inside
        elif selector.combinator == '>':
            # Empty list for False, non-empty list for True
            # Use list(generator-expression) rather than [list-comprehension]
            # to create a new scope for the el variable.
            # List comprehensions do not create a scope in Python 2.x
            left = ('list(1 for el in [el.parent] '
                         'if el is not None and %s)' % left_inside)
        elif selector.combinator == '+':
            left = ('list(1 for el in [el.previous] '
                         'if el is not None and %s)' % left_inside)
        elif selector.combinator == '~':
            left = ('any(%s for el in el.iter_previous_siblings())'
                    % left_inside)
        else:
            raise ValueError('Unknown combinator', selector.combinator)

        right = _compile_node(selector.right)
        if right == '0':
            return '0'  # 0 and x == 0
        elif right == '1':
            return left  # 1 and x == x
        else:
            # Evaluate combinators right to left:
            return '(%s and %s)' % (right, left)

    elif isinstance(selector, parser.CompoundSelector):
        sub_expressions = [
            expr for expr in map(_compile_node, selector.simple_selectors)
            if expr != '1']
        if len(sub_expressions) == 1:
            test = sub_expressions[0]
        elif '0' in sub_expressions:
            test = '0'
        elif sub_expressions:
            test = '(%s)' % ' and '.join(sub_expressions)
        else:
            test = '1'  # all([]) == True

        if isinstance(selector, parser.NegationSelector):
            if test == '0':
                return '1'
            elif test == '1':
                return '0'
            else:
                return '(not %s)' % test
        else:
            return test

    elif isinstance(selector, parser.LocalNameSelector):
        return '(el.local_name == %r)' % selector.local_name

    elif isinstance(selector, parser.NamespaceSelector):
        return '(el.namespace_url == %r)' % selector.namespace

    elif isinstance(selector, parser.ClassSelector):
        return '(%r in el.classes)' % selector.class_name

    elif isinstance(selector, parser.IDSelector):
        return '(el.id == %r)' % selector.ident

    elif isinstance(selector, parser.AttributeSelector):
        if selector.namespace is not None:
            if selector.namespace:
                key = '{%s}%s' % (selector.namespace, selector.name)
            else:
                key = selector.name
            value = selector.value
            if selector.operator is None:
                return '(el.get_attr(%r) is not None)' % key
            elif selector.operator == '=':
                return '(el.get_attr(%r) == %r)' % (key, value)
            elif selector.operator == '~=':
                if len(value.split()) != 1 or value.strip() != value:
                    return '0'
                else:
                    return ('(%r in split_whitespace(el.get_attr(%r, "")))'
                            % (value, key))
            elif selector.operator == '|=':
                # Empty list for False, non-empty list for True
                return ('[1 for value in [el.get_attr(%r)] if value == %r or'
                        ' (value is not None and value.startswith(%r))]'
                        % (key, value, value + '-'))
            elif selector.operator == '^=':
                if value:
                    return 'el.get_attr(%r, "").startswith(%r)' % (key, value)
                else:
                    return '0'
            elif selector.operator == '$=':
                if value:
                    return 'el.get_attr(%r, "").endswith(%r)' % (key, value)
                else:
                    return '0'
            elif selector.operator == '*=':
                if value:
                    return '(%r in el.get_attr(%r, ""))' % (value, key)
                else:
                    return '0'
            else:
                raise ValueError(
                    'Unknown attribute operator', selector.operator)
        else:  # In any namespace
            raise NotImplementedError  # TODO

    elif isinstance(selector, parser.PseudoClassSelector):
        if selector.name == 'link':
            # XXX HTML-only
            return _compile_node('a[href]')
        elif selector.name in ('visited', 'hover', 'active', 'focus',
                                'target'):
            # Not applicable in a static context: never match.
            return '0'
        elif selector.name in ('enabled', 'disabled', 'checked'):
            # TODO
            return '0'
        elif selector.name == 'root':
            return '(el.parent is None)'
        elif selector.name == 'first-child':
            return '(el.parent is not None and el.previous is None)'
        elif selector.name == 'last-child':
            return ('(el.parent is not None and '
                    'el.index + 1 == len(el.parent.etree_children))')
        elif selector.name == 'first-of-type':
            return ('(el.parent is not None and '
                    'all(s.tag != el.etree_element.tag'
                    '    for s in el.parent.etree_children[:el.index]))')
        elif selector.name == 'last-of-type':
            return ('(el.parent is not None and '
                    'all(s.tag != el.etree_element.tag'
                    '    for s in el.parent.etree_children[el.index + 1:]))')
        elif selector.name == 'only-child':
            return ('(el.parent is not None and '
                    ' len(el.parent.etree_children) == 1)')
        elif selector.name == 'only-of-type':
            return ('(el.parent is not None and '
                    'all(s.tag != el.etree_element.tag'
                    '    for s in el.parent.etree_children[:el.index]'
                    '           + el.parent.etree_children[el.index + 1:]))')
        elif selector.name == 'empty':
            return '(not (el.etree_children or el.etree_element.text))'
        else:
            raise ValueError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, parser.FunctionalPseudoClassSelector):
        if selector.name == 'lang':
            tokens = [
                t for t in selector.arguments
                if t.type != 'whitespace'
            ]
            if len(tokens) == 1 and tokens[0].type == 'ident':
                lang = tokens[0].value
            else:
                raise ValueError('Invalid arguments for :lang()')

            # TODO: matching should be case-insensitive
            return ('(el.lang is not None and '
                    ' (el.lang == %r or el.lang.startswith(%r)))'
                    % (lang, lang + '-'))
        else:
            result = parse_nth(selector.arguments)
            if result is None:
                raise ValueError('Invalid arguments for :%s()' % selector.name)
            a, b = result
            # x is the number of siblings before/after the element
            # Matches if a positive or zero integer n exists so that:
            # x = a*n + b-1
            # x = a*n + B
            B = b - 1
            if a == 0:
                # x = B
                test = '(el.parent is not None and (%%s) == %i)' % B
            else:
                # n = (x - B) / a
                # Empty list for False, non-empty list for True
                test = ('(el.parent is not None and '
                        ' [1 for n, r in [divmod((%%s) - %i, %i)]'
                        '  if r == 0 and n >= 0])'
                        % (B, a))

            if selector.name == 'nth-child':
                return test % 'el.index'
            elif selector.name == 'nth-last-child':
                return test % 'len(el.parent.etree_children) - el.index - 1'
            elif selector.name == 'nth-of-type':
                return test % (
                    'sum(1 for s in el.parent.etree_children[:el.index]'
                    '    if s.tag == el.etree_element.tag)')
            elif selector.name == 'nth-last-of-type':
                return test % (
                    'sum(1 for s in el.parent.etree_children[el.index + 1:]'
                    '    if s.tag == el.etree_element.tag)')
            else:
                raise ValueError('Unknown pseudo-class', selector.name)

    else:
        raise TypeError(type(selector), selector)