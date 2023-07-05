"""Compile CSS4 selectors into boolean evaluator functions, operating on ElementWrapper"""

import re
from typing import Union
from urllib.parse import urlparse

from tinycss2.nth import parse_nth
from webencodings import ascii_lower

from . import parser
from .parser import SelectorError

# http://dev.w3.org/csswg/selectors/#whitespace
split_whitespace = re.compile('[^ \t\r\n\f]+').findall


def compile_selector_list(input, namespaces=None): #pylint: disable=redefined-builtin
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

#pylint: disable=comparison-with-callable, too-many-instance-attributes, invalid-name
class CompiledSelector:
    """Abstract representation of a selector."""
    def __init__(self, parsed_selector):
        source = _compile_node(parsed_selector.parsed_tree)
        self.never_matches = source == FALSE
        self.test = source
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
            elif isinstance(simple_selector, parser.AttributeSelector):
                if simple_selector.name == 'lang':
                    self.requires_lang_attr = True

def FALSE(_el):
    """Always returns 0"""
    return 0
def TRUE(_el):
    """Always returns 1"""
    return 1



def _compile_combined(selector: parser.CombinedSelector):
    left_inside = _compile_node(selector.left)
    if left_inside == FALSE:
        return FALSE  # 0 and x == 0
    if left_inside == TRUE:
        # 1 and x == x, but the element matching 1 still needs to exist.
        if selector.combinator in (' ', '>'):
            def left(el):
                return el.parent is not None
        elif selector.combinator in ('~', '+'):
            def left(el):
                return el.previous is not None
        else:
            raise SelectorError('Unknown combinator', selector.combinator)
    elif selector.combinator == ' ':
        def left(el):
            return any((left_inside(e)) for e in el.ancestors)
    elif selector.combinator == '>':
        def left(el):
            return el.parent is not None and left_inside(el.parent)
    elif selector.combinator == '+':
        def left(el):
            return el.previous is not None and left_inside(el.previous)
    elif selector.combinator == '~':
        def left(el):
            return any((left_inside(e)) for e in el.previous_siblings)
    else:
        raise SelectorError('Unknown combinator', selector.combinator)

    right = _compile_node(selector.right)
    if right == FALSE:
        return FALSE  # 0 and x == 0
    if right == TRUE:
        return left  # 1 and x == x
    # Evaluate combinators right to left
    return lambda el: right(el) and left(el)

def _compile_compound(selector: parser.CompoundSelector):
    sub_expressions = [
        expr for expr in map(_compile_node, selector.simple_selectors)
        if expr != TRUE]
    if len(sub_expressions) == 1:
        return sub_expressions[0]
    if FALSE in sub_expressions:
        return FALSE
    if sub_expressions:
        return lambda e: all(expr(e) for expr in sub_expressions)
    return TRUE  # all([]) == True

def _compile_negation(selector: parser.NegationSelector):
    sub_expressions = [
        expr for expr in [
            _compile_node(selector.parsed_tree)
            for selector in selector.selector_list]
        if expr != TRUE]
    if not sub_expressions:
        return FALSE
    return lambda el: not any(expr(el) for expr in sub_expressions)


def _get_subexpr(expression, relative_selector):
    """Helper function for RelationalSelector"""
    if relative_selector.combinator == ' ':
        def check(el):
            subels = el.iter_subtree()
            # Skip self (only look at descendants)
            next(subels)
            return any(expression(e) for e in subels)
        return check
    if relative_selector.combinator == '>':
        return lambda el: any(expression(e) for e in el.iter_children())
    if relative_selector.combinator == '+':
        return lambda el: expression(next(el.iter_next_siblings()))
    if relative_selector.combinator == '~':
        return lambda el: any(expression(e) for e in el.iter_next_siblings())
    raise SelectorError(f"Unknown relational selector '{relative_selector.combinator}'")

def _compile_relational(selector: parser.RelationalSelector):
    sub_expr = []

    for relative_selector in selector.selector_list:
        expression = _compile_node(relative_selector.selector.parsed_tree)
        if expression == FALSE:
            continue
        sub_expr.append(_get_subexpr(expression, relative_selector))
    return lambda el: any(expr(el) for expr in sub_expr)

def _compile_any(selector: Union[parser.MatchesAnySelector, parser.SpecificityAdjustmentSelector]):
    sub_expressions = [
        expr for expr in [
            _compile_node(selector.parsed_tree)
            for selector in selector.selector_list]
        if expr != FALSE]
    if not sub_expressions:
        return FALSE
    return lambda el: any(expr(el) for expr in sub_expressions)

def _compile_local_name(selector: parser.LocalNameSelector):
    if selector.lower_local_name == selector.local_name:
        return lambda el: el.local_name == selector.local_name
    return lambda el: el.local_name == (
        selector.lower_local_name if el.in_html_document else selector.local_name)

def _compile_namespace(selector: parser.NamespaceSelector):
    return lambda el: el.namespace_url == selector.namespace

def _compile_class(selector: parser.ClassSelector):
    return lambda el: selector.class_name in el.classes

def _compile_id(selector: parser.IDSelector):
    return lambda el: el.id == selector.ident

def _compile_attribute(selector: parser.AttributeSelector):
    if selector.namespace is not None:
        if selector.namespace:
            if selector.name == selector.lower_name:
                def key_func(_el):
                    return f'{{{selector.namespace}}}{selector.name}'
            else:
                lower = f'{{{selector.namespace}}}{selector.lower_name}'
                name = f'{{{selector.namespace}}}{selector.name}'
                def key_func(el):
                    return (lower if el.in_html_document else name)
        else:
            if selector.name == selector.lower_name:
                def key_func(_el):
                    return selector.name
            else:
                lower, name = selector.lower_name, selector.name
                def key_func(el):
                    return lower if el.in_html_document else name
        value = selector.value
        if selector.case_sensitive is False:
            value = value.lower()
            def attribute_value(el):
                return el.etree_element.get(key_func(el), "").lower()
        else:
            def attribute_value(el):
                return el.etree_element.get(key_func(el), "")
        if selector.operator is None:
            return lambda el: key_func(el) in el.etree_element.attrib
        if selector.operator == '=':
            return lambda el: (key_func(el) in el.etree_element.attrib and
                                attribute_value(el) == value)
        if selector.operator == '~=':
            return (FALSE if len(value.split()) != 1 or value.strip() != value
                    else lambda el: value in split_whitespace(attribute_value(el)))
        if selector.operator == '|=':
            return lambda el: (key_func(el) in el.etree_element.attrib and
                                (attribute_value(el) == value or
                                attribute_value(el).startswith(value + "-") ))
        if selector.operator == '^=':
            if value:
                return lambda el:  attribute_value(el).startswith(value)
            return FALSE
        if selector.operator == '$=':
            return (lambda el:  attribute_value(el).endswith(value)) if value else FALSE
        if selector.operator == '*=':
            return (lambda el:  value in attribute_value(el)) if value else FALSE
        raise SelectorError('Unknown attribute operator', selector.operator)
    # In any namespace
    raise NotImplementedError  # TODO

def _compile_pseudoclass(selector: parser.PseudoClassSelector):
    if selector.name in ('link', 'any-link', 'local-link'):
        def test(el):
            return (html_tag_eq('a', 'area', 'link')(el) and
                    el.etree_element.get("href") is not None)
        if selector.name == 'local-link':
            return lambda el: test(el) and not urlparse(el.etree_element.get("href")).scheme
        return test
    if selector.name == 'enabled':
        return lambda el: (
            (html_tag_eq('button', 'input', 'select', 'textarea', 'option')(el) and
                (el.etree_element.get("disabled") is None) and not el.in_disabled_fieldset) or
            (html_tag_eq('optgroup', 'menuitem', 'fieldset')(el) and
                el.etree_element.get("disabled") is None) or
            (html_tag_eq('a', 'area', 'link')(el) and el.etree_element.get("href") is not None))
    if selector.name == 'disabled':
        return lambda el: (
            (html_tag_eq('button', 'input', 'select', 'textarea', 'option')(el) and
                (el.etree_element.get("disabled") is not None or el.in_disabled_fieldset)) or
            (html_tag_eq('optgroup', 'menuitem', 'fieldset')(el) and
                el.etree_element.get("disabled") is not None))
    if selector.name == 'checked':
        return lambda el: (
            (html_tag_eq('input', 'menuitem')(el) and
                el.etree_element.get("checked") is not None and
                ascii_lower(el.etree_element.get("type", "")) in ("checkbox", "radio")) or
            (html_tag_eq('option')(el) and el.etree_element.get("selected") is not None))
    if selector.name in (
            'visited', 'hover', 'active', 'focus', 'focus-within',
            'focus-visible', 'target', 'target-within', 'current', 'past',
            'future', 'playing', 'paused', 'seeking', 'buffering',
            'stalled', 'muted', 'volume-locked', 'user-valid',
            'user-invalid'):
        # Not applicable in a static context: never match.
        return FALSE
    if selector.name in ('root', 'scope'):
        return lambda el: el.parent is None
    if selector.name == 'first-child':
        return lambda el: el.index == 0
    if selector.name == 'last-child':
        return lambda el: el.index + 1 == len(el.etree_siblings)
    if selector.name == 'first-of-type':
        return lambda el: all(s.tag != el.etree_element.tag
                                for s in el.etree_siblings[:el.index])
    if selector.name == 'last-of-type':
        return lambda el: all(s.tag != el.etree_element.tag
                                for s in el.etree_siblings[el.index + 1:])
    if selector.name == 'only-child':
        return lambda el: len(el.etree_siblings) == 1
    if selector.name == 'only-of-type':
        return lambda el: all(s.tag != el.etree_element.tag or i == el.index
                                for i, s in enumerate(el.etree_siblings))
    if selector.name == 'empty':
        return lambda el: not (el.etree_children or el.etree_element.text)
    raise SelectorError('Unknown pseudo-class', selector.name)

def _compile_lang(selector: parser.FunctionalPseudoClassSelector):
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
    return lambda el: any(el.lang == lang or el.lang.startswith(lang + "-")
                            for lang in langs)

def _compile_functional_pseudoclass(selector: parser.FunctionalPseudoClassSelector):
    if selector.name == 'lang':
        return _compile_lang(selector)
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
        compiled = tuple(_compile_node(selector.parsed_tree)
            for selector in parser.parse(selector_list))
        def test(el):
            return all(expr(el) for expr in compiled)
        if selector.name == 'nth-child':
            def count(el):
                return sum(1 for e in el.previous_siblings if test(e))
        elif selector.name == 'nth-last-child':
            def count(el):
                return sum(1 for e in tuple(el.iter_siblings())[el.index + 1:] if test(e))
        elif selector.name == 'nth-of-type':
            def count(el):
                return (sum(1 for s in (e for e in el.previous_siblings if test(e))
                            if s.etree_element.tag == el.etree_element.tag))
        elif selector.name == 'nth-last-of-type':
            def count(el):
                return (sum(1 for s in (e for e in tuple(el.iter_siblings())[el.index + 1:]
                                        if test(e))
                            if s.etree_element.tag == el.etree_element.tag))
        else:
            raise SelectorError('Unknown pseudo-class', selector.name)
        def count_func(el):
            return count(el) if test(el) else float("nan")
    else:
        if current_list is selector_list:
            raise SelectorError(
                f'Invalid arguments for :{selector.name}()')
        if selector.name == 'nth-child':
            def count_func(el):
                return el.index
        elif selector.name == 'nth-last-child':
            def count_func(el):
                return len(el.etree_siblings) - el.index - 1
        elif selector.name == 'nth-of-type':
            def count_func(el):
                return sum(1 for s in el.etree_siblings[:el.index] if s.tag == el.etree_element.tag)
        elif selector.name == 'nth-last-of-type':
            def count_func(el):
                return sum(1 for s in el.etree_siblings[el.index + 1:]
                            if s.tag == el.etree_element.tag)
        else:
            raise SelectorError('Unknown pseudo-class', selector.name)

    result = parse_nth(nth)
    if result is None:
        raise SelectorError(
            f'Invalid arguments for :{selector.name}()')
    a, b = result
    # x is the number of siblings before/after the element
    # Matches if a positive or zero integer n exists so that:
    # x = a*n + b-1
    # x = a*n + B
    B = b - 1
    if a == 0:
        # x = B
        return lambda el: count_func(el) == B
    # n = (x - B) / a
    def evaluator(el):
        n, r = divmod(count_func(el) - B, a)
        return r == 0 and n >= 0
    return evaluator

_func_map = {
    parser.CombinedSelector : _compile_combined,
    parser.CompoundSelector : _compile_compound,
    parser.NegationSelector : _compile_negation,
    parser.RelationalSelector : _compile_relational,
    parser.MatchesAnySelector : _compile_any,
    parser.SpecificityAdjustmentSelector : _compile_any,
    parser.LocalNameSelector : _compile_local_name,
    parser.NamespaceSelector : _compile_namespace,
    parser.ClassSelector : _compile_class,
    parser.IDSelector : _compile_id,
    parser.AttributeSelector : _compile_attribute,
    parser.PseudoClassSelector : _compile_pseudoclass,
    parser.FunctionalPseudoClassSelector : _compile_functional_pseudoclass
}

def _compile_node(selector):
    """Return a boolean expression, as a callable.

    When evaluated in a context where the `el` variable is an
    :class:`cssselect2.tree.Element` object, tells whether the element is a
    subject of `selector`.

    """
    try:
        return _func_map[selector.__class__](selector)
    except KeyError as e:
        raise TypeError(type(selector), selector) from e

def html_tag_eq(*local_names):
    """Generate expression testing equality with HTML local names."""
    if len(local_names) == 1:
        tag = '{http://www.w3.org/1999/xhtml}' + local_names[0]
        return lambda el: ((el.local_name == local_names[0])
                           if el.in_html_document else (el.etree_element.tag == tag))
    tags = ('{http://www.w3.org/1999/xhtml}' + n for n in local_names)
    return lambda el: ((el.local_name in local_names)
                        if el.in_html_document else (el.etree_element.tag in tags))
