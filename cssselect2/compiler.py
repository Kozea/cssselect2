import re
from urllib.parse import urlparse

from tinycss2.nth import parse_nth
from webencodings import ascii_lower

from . import parser
from .parser import SelectorError

# http://dev.w3.org/csswg/selectors/#whitespace
split_whitespace = re.compile('[^ \t\r\n\f]+').findall


def compile_selector_list(input, namespaces=None):
    """Compile a (comma-separated) list of selectors.

    :param input:
        A string, or an iterable of tinycss2 component values such as
        the :attr:`tinycss2.ast.QualifiedRule.prelude` of a style rule.
    :param namespaces:
        A optional dictionary of all `namespace prefix declarations
        <http://www.w3.org/TR/selectors/#nsdecl>`_ in scope for this selector.
        Keys are namespace prefixes as strings, or ``None`` for the default
        namespace.
        Values are namespace URLs as strings.
        If omitted, assume that no prefix is declared.
    :returns:
        A list of opaque :class:`compiler.CompiledSelector` objects.

    """
    return [
        CompiledSelector(selector)
        for selector in parser.parse(input, namespaces)
    ]


class CompiledSelector(object):
    """Abstract representation of a selector."""
    def __init__(self, parsed_selector):
        source = _compile_node(parsed_selector.parsed_tree)
        self.never_matches = source == '0'
        eval_globals = {
            'split_whitespace': split_whitespace,
            'ascii_lower': ascii_lower,
            'urlparse': urlparse,
        }
        self.test = eval('lambda el: ' + source, eval_globals, {})
        self.specificity = parsed_selector.specificity
        self.pseudo_element = parsed_selector.pseudo_element
        self.id = None
        self.class_name = None
        self.local_name = None
        self.lower_local_name = None
        self.namespace = None
        self.requires_lang_attr = False

        node = parsed_selector.parsed_tree
        if isinstance(node, parser.CombinedSelector):
            node = node.right
        for simple_selector in node.simple_selectors:
            if isinstance(simple_selector, parser.IDSelector):
                self.id = simple_selector.ident
            elif isinstance(simple_selector, parser.ClassSelector):
                self.class_name = simple_selector.class_name
            elif isinstance(simple_selector, parser.LocalNameSelector):
                self.local_name = simple_selector.local_name
                self.lower_local_name = simple_selector.lower_local_name
            elif isinstance(simple_selector, parser.NamespaceSelector):
                self.namespace = simple_selector.namespace
            elif isinstance(simple_selector, parser.AttributeSelector) and \
                    simple_selector.name == "lang":
                self.requires_lang_attr = True


def _compile_node(selector):
    """Return a boolean expression, as a Python source string.

    When evaluated in a context where the `el` variable is an
    :class:`cssselect2.tree.Element` object,
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
                left = 'el.parent is not None'
            elif selector.combinator in ('~', '+'):
                left = 'el.previous is not None'
            else:
                raise SelectorError('Unknown combinator', selector.combinator)
        # Rebind the `el` name inside a generator-expressions (in a new scope)
        # so that 'left_inside' applies to different elements.
        elif selector.combinator == ' ':
            left = 'any((%s) for el in el.iter_ancestors())' % left_inside
        elif selector.combinator == '>':
            left = ('next(el is not None and (%s) for el in [el.parent])'
                    % left_inside)
        elif selector.combinator == '+':
            left = ('next(el is not None and (%s) for el in [el.previous])'
                    % left_inside)
        elif selector.combinator == '~':
            left = ('any((%s) for el in el.iter_previous_siblings())'
                    % left_inside)
        else:
            raise SelectorError('Unknown combinator', selector.combinator)

        right = _compile_node(selector.right)
        if right == '0':
            return '0'  # 0 and x == 0
        elif right == '1':
            return left  # 1 and x == x
        else:
            # Evaluate combinators right to left:
            return '(%s) and (%s)' % (right, left)

    elif isinstance(selector, parser.CompoundSelector):
        sub_expressions = [
            expr for expr in map(_compile_node, selector.simple_selectors)
            if expr != '1']
        if len(sub_expressions) == 1:
            test = sub_expressions[0]
        elif '0' in sub_expressions:
            test = '0'
        elif sub_expressions:
            test = ' and '.join('(%s)' % e for e in sub_expressions)
        else:
            test = '1'  # all([]) == True
        return test

    elif isinstance(selector, parser.NegationSelector):
        sub_expressions = [
            expr for expr in map(_compile_node, selector.selector_list)
            if expr != '1']
        if not sub_expressions:
            return '0'
        return f'not ({" or ".join(f"({expr})" for expr in sub_expressions)})'

    elif isinstance(selector, (
            parser.MatchesAnySelector, parser.SpecificityAdjustmentSelector)):
        sub_expressions = [
            expr for expr in map(_compile_node, selector.selector_list)
            if expr != '0']
        if not sub_expressions:
            return '0'
        return ' or '.join(f'({expr})' for expr in sub_expressions)

    elif isinstance(selector, parser.LocalNameSelector):
        if selector.lower_local_name == selector.local_name:
            return 'el.local_name == %r' % selector.local_name
        else:
            return (
                'el.local_name == (%r if el.in_html_document else %r)' %
                (selector.lower_local_name, selector.local_name))

    elif isinstance(selector, parser.NamespaceSelector):
        return 'el.namespace_url == %r' % selector.namespace

    elif isinstance(selector, parser.ClassSelector):
        return '%r in el.classes' % selector.class_name

    elif isinstance(selector, parser.IDSelector):
        return 'el.id == %r' % selector.ident

    elif isinstance(selector, parser.AttributeSelector):
        if selector.namespace is not None:
            if selector.namespace:
                if selector.name == selector.lower_name:
                    key = repr('{%s}%s' % (selector.namespace, selector.name))
                else:
                    key = '(%r if el.in_html_document else %r)' % (
                        '{%s}%s' % (selector.namespace, selector.lower_name),
                        '{%s}%s' % (selector.namespace, selector.name),
                    )
            else:
                if selector.name == selector.lower_name:
                    key = repr(selector.name)
                else:
                    key = '(%r if el.in_html_document else %r)' % (
                        selector.lower_name, selector.name)
            value = selector.value
            if selector.operator is None:
                return '%s in el.etree_element.attrib' % key
            elif selector.operator == '=':
                return 'el.etree_element.get(%s) == %r' % (key, value)
            elif selector.operator == '~=':
                if len(value.split()) != 1 or value.strip() != value:
                    return '0'
                else:
                    return (
                        '%r in split_whitespace(el.etree_element.get(%s, ""))'
                        % (value, key))
            elif selector.operator == '|=':
                return ('next(v == %r or (v is not None and v.startswith(%r))'
                        '     for v in [el.etree_element.get(%s)])'
                        % (value, value + '-', key))
            elif selector.operator == '^=':
                if value:
                    return 'el.etree_element.get(%s, "").startswith(%r)' % (
                        key, value)
                else:
                    return '0'
            elif selector.operator == '$=':
                if value:
                    return 'el.etree_element.get(%s, "").endswith(%r)' % (
                        key, value)
                else:
                    return '0'
            elif selector.operator == '*=':
                if value:
                    return '%r in el.etree_element.get(%s, "")' % (value, key)
                else:
                    return '0'
            else:
                raise SelectorError(
                    'Unknown attribute operator', selector.operator)
        else:  # In any namespace
            raise NotImplementedError  # TODO

    elif isinstance(selector, parser.PseudoClassSelector):
        if selector.name in ('link', 'any-link', 'local-link'):
            test = '%s and el.etree_element.get("href") is not None '
            if selector.name == 'local-link':
                test += 'and not urlparse(el.etree_element.get("href")).scheme'
            return test % html_tag_eq('a', 'area', 'link')
        elif selector.name == 'enabled':
            return (
                '(%s and el.etree_element.get("disabled") is None'
                ' and not el.in_disabled_fieldset) or'
                '(%s and el.etree_element.get("disabled") is None) or '
                '(%s and el.etree_element.get("href") is not None)'
                % (
                    html_tag_eq('button', 'input', 'select', 'textarea',
                                'option'),
                    html_tag_eq('optgroup', 'menuitem', 'fieldset'),
                    html_tag_eq('a', 'area', 'link'),
                )
            )
        elif selector.name == 'disabled':
            return (
                '(%s and (el.etree_element.get("disabled") is not None'
                ' or el.in_disabled_fieldset)) or'
                '(%s and el.etree_element.get("disabled") is not None)' % (
                    html_tag_eq('button', 'input', 'select', 'textarea',
                                'option'),
                    html_tag_eq('optgroup', 'menuitem', 'fieldset'),
                )
            )
        elif selector.name == 'checked':
            return (
                '(%s and el.etree_element.get("checked") is not None and'
                ' ascii_lower(el.etree_element.get("type", "")) '
                ' in ("checkbox", "radio"))'
                'or (%s and el.etree_element.get("selected") is not None)'
                % (
                    html_tag_eq('input', 'menuitem'),
                    html_tag_eq('option'),
                )
            )
        elif selector.name in (
                'visited', 'hover', 'active', 'focus', 'focus-within',
                'focus-visible', 'target', 'target-within', 'current', 'past',
                'future', 'playing', 'paused', 'seeking', 'buffering',
                'stalled', 'muted', 'volume-locked', 'user-valid',
                'user-invalid'):
            # Not applicable in a static context: never match.
            return '0'
        elif selector.name in ('root', 'scope'):
            return 'el.parent is None'
        elif selector.name == 'first-child':
            return 'el.index == 0'
        elif selector.name == 'last-child':
            return 'el.index + 1 == len(el.etree_siblings)'
        elif selector.name == 'first-of-type':
            return ('all(s.tag != el.etree_element.tag'
                    '    for s in el.etree_siblings[:el.index])')
        elif selector.name == 'last-of-type':
            return ('all(s.tag != el.etree_element.tag'
                    '    for s in el.etree_siblings[el.index + 1:])')
        elif selector.name == 'only-child':
            return 'len(el.etree_siblings) == 1'
        elif selector.name == 'only-of-type':
            return ('all(s.tag != el.etree_element.tag or i == el.index'
                    '    for i, s in enumerate(el.etree_siblings))')
        elif selector.name == 'empty':
            return 'not (el.etree_children or el.etree_element.text)'
        else:
            raise SelectorError('Unknown pseudo-class', selector.name)

    elif isinstance(selector, parser.FunctionalPseudoClassSelector):
        if selector.name == 'lang':
            langs = []
            tokens = [
                token for token in selector.arguments
                if token.type not in ('whitespace', 'comment')]
            while tokens:
                token = tokens.pop(0)
                if token.type == 'ident':
                    langs.append(token.lower_value)
                elif token.type == 'string':
                    langs.append(ascii_lower(token.value))
                else:
                    raise SelectorError('Invalid arguments for :lang()')
                if tokens:
                    token = tokens.pop(0)
                    if token.type != 'ident' and token.value != ',':
                        raise SelectorError('Invalid arguments for :lang()')
            return ' or '.join(
                f'el.lang == {lang!r} or el.lang.startswith({lang + "-"!r})'
                for lang in langs)
        else:
            nth = []
            selector_list = []
            current_list = nth
            for argument in selector.arguments:
                if argument.type == 'ident' and argument.value == 'of':
                    if current_list is nth:
                        current_list = selector_list
                        continue
                current_list.append(argument)

            if selector_list:
                test = ' and '.join(
                    _compile_node(selector.parsed_tree)
                    for selector in parser.parse(selector_list))
                if selector.name == 'nth-child':
                    count = (
                        'sum(1 for el in el.iter_previous_siblings()'
                        f'   if ({test}))')
                elif selector.name == 'nth-last-child':
                    count = (
                        'sum(1 for el in'
                        '    tuple(el.iter_siblings())[el.index + 1:]'
                        f'   if ({test}))')
                elif selector.name == 'nth-of-type':
                    count = (
                        'sum(1 for s in ('
                        '      el for el in el.iter_previous_siblings()'
                        f'     if ({test}))'
                        '    if s.etree_element.tag == el.etree_element.tag)')
                elif selector.name == 'nth-last-of-type':
                    count = (
                        'sum(1 for s in ('
                        '      el for el in'
                        '      tuple(el.iter_siblings())[el.index + 1:]'
                        f'     if ({test}))'
                        '    if s.etree_element.tag == el.etree_element.tag)')
                else:
                    raise SelectorError('Unknown pseudo-class', selector.name)
                count += f'if ({test}) else float("nan")'
            else:
                if current_list is selector_list:
                    raise SelectorError(
                        'Invalid arguments for :%s()' % selector.name)
                if selector.name == 'nth-child':
                    count = 'el.index'
                elif selector.name == 'nth-last-child':
                    count = 'len(el.etree_siblings) - el.index - 1'
                elif selector.name == 'nth-of-type':
                    count = ('sum(1 for s in el.etree_siblings[:el.index]'
                             '    if s.tag == el.etree_element.tag)')
                elif selector.name == 'nth-last-of-type':
                    count = ('sum(1 for s in el.etree_siblings[el.index + 1:]'
                             '    if s.tag == el.etree_element.tag)')
                else:
                    raise SelectorError('Unknown pseudo-class', selector.name)

            result = parse_nth(nth)
            if result is None:
                raise SelectorError(
                    'Invalid arguments for :%s()' % selector.name)
            a, b = result
            # x is the number of siblings before/after the element
            # Matches if a positive or zero integer n exists so that:
            # x = a*n + b-1
            # x = a*n + B
            B = b - 1
            if a == 0:
                # x = B
                return '(%s) == %i' % (count, B)
            else:
                # n = (x - B) / a
                return ('next(r == 0 and n >= 0'
                        '     for n, r in [divmod((%s) - %i, %i)])'
                        % (count, B, a))

    else:
        raise TypeError(type(selector), selector)


def html_tag_eq(*local_names):
    if len(local_names) == 1:
        return (
            '((el.local_name == %r) if el.in_html_document else '
            '(el.etree_element.tag == %r))' % (
                local_names[0],
                '{http://www.w3.org/1999/xhtml}' + local_names[0]))
    else:
        return (
            '((el.local_name in (%s)) if el.in_html_document else '
            '(el.etree_element.tag in (%s)))' % (
                ', '.join(repr(n) for n in local_names),
                ', '.join(repr('{http://www.w3.org/1999/xhtml}' + n)
                          for n in local_names)))
