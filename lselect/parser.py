# coding: utf8
"""
    lselect.parser
    --------------

    A parser for CSS selectors, based on the tinycss tokenizer.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

import re

from tinycss.tokenizer import tokenize_grouped
from tinycss.parsing import ParseError, strip_whitespace


__all__ = ['parse_string', 'parse']


def parse_string(string, namespaces=None):
    if isinstance(string, bytes):
        string = string.decode('ascii')
    return list(parse(tokenize_grouped(string), namespaces))


def parse(tokens, namespaces=None):
    tokens = TokenStream(tokens)
    namespaces = namespaces or {}
    selectors = []
    selectors.append(parse_selector(tokens, namespaces))
    while 1:
        next = tokens.next()
        if next.type == 'EOF':
            return selectors
        elif next.type == ',':
            selectors.append(parse_selector(tokens, namespaces))
        else:
            raise SelectorError(next, 'unpexpected %s token.' % next.type)


# ['-'|'+']? INTEGER? {N} [ S* ['-'|'+'] S* INTEGER ]?
NTH_CHILD_RE = re.compile(
    r'^([-+]?)(\d+)?{n}({w}[-+]{w}\d+)?$'.format(
        n=r'(?:n|\\0{0,4}(?:4e|6e)(?:\r\n|[ \t\r\n\f])?|\\n)',
        w=r'[ \t\r\n\f]*'))

def parse_nth_child(tokens):
    """Parse the arguments for :nth-child() and friends.

    :param tokens: A list of tokens
    :returns: ``(a, b)`` or None

    """
    tokens = strip_whitespace(tokens)
    if len(tokens) == 1:
        type_ = tokens[0].type
        value = tokens[0].value
        if type_ == 'IDENT':
            if value == 'odd':
                return 2, 1
            if value == 'even':
                return 2, 0
        if type_ == 'INTEGER':
            return 0, value

    match = NTH_CHILD_RE.match(''.join(token.as_css() for token in tokens))
    if match:
        a_sign, a, b = match.groups()
        a = int(a) if a else 1
        if a_sign == '-':
            a = -a
        b = int(b) if b else 0
        return a, b


def parse_lang(tokens):
    """Parse the arguments for :lang().

    :param tokens: A list of tokens
    :returns: ``(a, b)`` or None

    """
    tokens = strip_whitespace(tokens)
    if len(tokens) == 1 and tokens[0].type == 'IDENT':
        return tokens[0].value


def parse_selector(tokens, namespaces):
    result, pseudo_element = parse_compound_selector(tokens, namespaces)
    while 1:
        has_whitespace = tokens.skip_whitespace()
        if pseudo_element is not None:
            return Selector(result, pseudo_element)
        peek = tokens.peek()
        if peek.type in ('>', '+', '~'):
            combinator = peek.type
            tokens.next()
        elif has_whitespace and peek.type != 'EOF':
            combinator = ' '
        else:
            return Selector(result, pseudo_element)
        compound, pseudo_element = parse_compound_selector(tokens, namespaces)
        result = CombinedSelector(result, combinator, compound)


def parse_compound_selector(tokens, namespaces):
    simple_selectors = []
    pseudo_element = None

    tokens.skip_whitespace()
    peek3 = tokens.peek_types(3)
    peek2 = peek3[:2]
    peek1 = peek3[0]
    if peek3 == ('IDENT', '|', 'IDENT'):
        namespace = get_namespace(tokens.next(), namespaces)
        tokens.next()
        element_type = tokens.next().value
        simple_selectors.append(ElementTypeSelector(namespace, element_type))
    elif peek3 == ('IDENT', '|', '*'):
        namespace = get_namespace(tokens.next(), namespaces)
        tokens.next()
        tokens.next()
        simple_selectors.append(UniversalSelector(namespace))
    elif peek1 == 'IDENT':
        namespace = namespaces.get(None, any)  # default namespace
        element_type = tokens.next().value
        simple_selectors.append(ElementTypeSelector(namespace, element_type))
    elif peek3 == ('*', '|', 'IDENT'):
        tokens.next()
        tokens.next()
        element_type = tokens.next().value
        simple_selectors.append(ElementTypeSelector(any, element_type))
    elif peek3 == ('*', '|', '*'):
        tokens.next()
        tokens.next()
        tokens.next()
        simple_selectors.append(UniversalSelector(any))
    elif peek1 == '*':
        namespace = namespaces.get(None, any)  # default namespace
        tokens.next()
        simple_selectors.append(UniversalSelector(namespace))
    elif peek2 == ('|', 'IDENT'):
        tokens.next()
        element_type = tokens.next().value
        simple_selectors.append(ElementTypeSelector(None, element_type))
    elif peek2 == ('|', '*'):
        tokens.next()
        tokens.next()
        simple_selectors.append(UniversalSelector(None))

    while 1:
        peek = tokens.peek()
        if peek.type == 'HASH':
            tokens.next()
            # [1:] removes the #
            simple_selectors.append(IDSelector(peek.value[1:]))
        elif peek.type == '.':
            tokens.next()
            simple_selectors.append(ClassSelector(get_ident(tokens.next())))
        elif peek.type == '[':
            tokens.next()
            simple_selectors.append(parse_attribute_selector(
                TokenStream(peek.content), namespaces))
        elif peek.type == ':':
            tokens.next()
            next = tokens.next()
            if next.type == ':':
                pseudo_element = get_ident(tokens.next())
                break
            elif next.type == 'IDENT':
                name = ascii_lower(next.value)
                if name in ('before', 'after', 'first-line', 'first-letter'):
                    pseudo_element = name
                    break
                else:
                    simple_selectors.append(PseudoClassSelector(name))
            elif next.type == 'FUNCTION':
                name = ascii_lower(next.function_name)
                if name == 'not':
                    simple_selectors.append(parse_negation(next, namespaces))
                else:
                    simple_selectors.append(FunctionalPseudoClassSelector(
                        name, next))
            else:
                raise SelectorError(next, 'unexpected %s token.' % next.type)
        else:
            break

    if simple_selectors:
        return CompoundSelector(simple_selectors), pseudo_element
    else:
        raise SelectorError(
            peek, 'expected a compound selector, got %s' % peek.type)


def parse_negation(negation_token, namespaces):
    tokens = TokenStream(negation_token.content)
    compound, pseudo_element = parse_compound_selector(tokens, namespaces)
    tokens.skip_whitespace()
    if (pseudo_element is None and len(compound.simple_selectors) == 1
            and tokens.next().type == 'EOF'):
        return NegationSelector(compound.simple_selectors[0])
    else:
        raise SelectorError(
            negation_token, ':not() only accepts a simple selector')


def parse_attribute_selector(tokens, namespaces):
    tokens.skip_whitespace()
    peek3 = tokens.peek_types(3)
    peek2 = peek3[:2]
    peek1 = peek3[0]
    if peek3 == ('IDENT', '|', 'IDENT'):
        namespace = get_namespace(tokens.next(), namespaces)
        tokens.next()
        name = tokens.next().value
    elif peek1 == 'IDENT':
        # The default namespace do not apply to attributes:
        # http://www.w3.org/TR/selectors/#attrnmsp
        namespace = None
        name = tokens.next().value
    elif peek3 == ('*', '|', 'IDENT'):
        namespace = any
        tokens.next()
        tokens.next()
        name = tokens.next().value
    elif peek2 == ('|', 'IDENT'):
        namespace = None
        tokens.next()
        name = tokens.next().value
    else:
        next = tokens.next()
        raise SelectorError(
            next, 'expected attribute name, got %s' % next.type)

    tokens.skip_whitespace()
    if tokens.peek().type == '=':
        operator = '='
        tokens.next()
    else:
        operator = ''.join(tokens.peek_types(2))
        if operator in ('~=', '|=', '^=', '$=', '*='):
            tokens.next()
            tokens.next()
        else:
            operator = value = None

    if operator is not None:
        tokens.skip_whitespace()
        next = tokens.next()
        if next.type not in ('IDENT', 'STRING'):
            raise SelectorError(
                next, 'expected attribute value, got %s' % next.type)
        value = next.value

    tokens.skip_whitespace()
    next = tokens.next().type
    if next != 'EOF':
        raise SelectorError(next, 'expected ], got %s' % next)
    return AttributeSelector(namespace, name, operator, value)


def get_namespace(token, namespaces):
    assert token.type == 'IDENT'
    prefix = token.value
    if prefix not in namespaces:
        raise SelectorError(token, 'undefined namespace prefix: ' + prefix)
    return namespaces[prefix]


def get_ident(token):
    if token.type != 'IDENT':
        raise SelectorError(token, 'Expected IDENT, got %s' % token.type)
    return token.value


def ascii_lower(string):
    """Lower-case, but only in the ASCII range."""
    return string.encode('utf8').lower().decode('utf8')


class SelectorError(ParseError):
    """A specialized ParseError from tinycss for selectors."""


class EOFToken(object):
    type = 'EOF'
    value = None


class TokenStream(object):
    def __init__(self, tokens):
        self.tokens = iter(tokens)
        self.peeked = []

    def _next(self):
        token = next(self.tokens, EOFToken)
        if token.type == 'DELIM':
            token.type = token.value
        return token

    def next(self):
        if self.peeked:
            return self.peeked.pop()
        else:
            return self._next()

    def peek_types(self, n):
        while len(self.peeked) < n:
            self.peeked.insert(0, self._next())
        return tuple(t.type for t in self.peeked[-n:][::-1])

    def peek(self):
        if not self.peeked:
            self.peeked.append(self._next())
        return self.peeked[-1]

    def skip_whitespace(self):
        has_whitespace = False
        while self.peek().type == 'S':
            self.next()
            has_whitespace = True
        return has_whitespace


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

    def __repr__(self):
        if self.pseudo_element is None:
            return repr(self.parsed_tree)
        else:
            return '%r::%s' % (self.parsed_tree, self.pseudo_element)



class CombinedSelector(object):
    def __init__(self, left, combinator, right):
        #: Combined or compound selector
        self.left = left
        # One of `` `` (a single space), ``>``, ``+`` or ``~``.
        self.combinator = combinator
        #: compound selector
        self.right = right

    @property
    def specificity(self):
        a1, b1, c1 = self.left.specificity
        a2, b2, c2 = self.right.specificity
        return a1 + a2, b1 + b2, c1 + c2

    def __repr__(self):
        return '%r%s%r' % (self.left, self.combinator, self.right)


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

    def __repr__(self):
        return ''.join(map(repr, self.simple_selectors))


class ElementTypeSelector(object):
    specificity =  0, 0, 1

    def __init__(self, namespace, element_type):
        #: Either ``None`` for no namespace, the built-in function
        #: ``any`` (used as a marker) for any namespace (``*`` in CSS)
        #: or a namespace name/URI (not a prefix) as a string.
        #:
        #: Note that simple type selectors like ``E`` are resolved to either
        #: ``NS|E`` or ``*|E``: http://www.w3.org/TR/selectors/#typenmsp
        self.namespace = namespace
        self.element_type = element_type

    def __repr__(self):
        if self.namespace is None:
            return '|' + self.element_type
        elif self.namespace is any:
            return '*|' + self.element_type
        else:
            return '{%s}|%s' % (self.namespace, self.element_type)


class UniversalSelector(object):
    specificity =  0, 0, 0

    def __init__(self, namespace):
        #: Same as :attr:`ElementTypeSelector.namespace`
        self.namespace = namespace

    def __repr__(self):
        if self.namespace is None:
            return '|*'
        elif self.namespace is any:
            return '*|*'
        else:
            return '{%s}|*' % self.namespace


class IDSelector(object):
    specificity =  1, 0, 0

    def __init__(self, ident):
        self.ident = ident

    def __repr__(self):
        return '#' + self.ident


class ClassSelector(object):
    specificity =  0, 1, 0

    def __init__(self, class_name):
        self.class_name = class_name

    def __repr__(self):
        return '.' + self.class_name


class AttributeSelector(object):
    specificity =  0, 1, 0

    def __init__(self, namespace, name, operator, value):
        #: Same as :attr:`ElementTypeSelector.namespace`
        self.namespace = namespace
        self.name = name
        #: A string like ``=`` or ``~=``, or None for ``[attr]`` selectors
        self.operator = operator
        #: A string, or None for ``[attr]`` selectors
        self.value = value

    def __repr__(self):
        namespace = '|' if self.namespace is None else (
            '*|' if self.namespace is any else '{%s}' % self.namespace)
        return '[%s%s%s%r]' % (namespace, self.name, self.operator, self.value)


class PseudoClassSelector(object):
    specificity =  0, 1, 0

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return ':' + self.name


class FunctionalPseudoClassSelector(object):
    specificity =  0, 1, 0

    def __init__(self, name, function_token):
        self.name = name
        self.function_token = function_token

    def __repr__(self):
        return ':%s%r' % (self.name, tuple(self.function_token.content))

    def parse(self, parse_function):
        result = parse_function(self.function_token.content)
        if result is None:
            raise SelectorError(self.function_token,
                                'invalid arguments for :%s()' % self.name)
        return result

    def parse_lang(self):
        return self.parse(parse_lang)

    def parse_nth_child(self):
        return self.parse(parse_nth_child)


class NegationSelector(object):
    def __init__(self, sub_selector):
        self.sub_selector = sub_selector

    @property
    def specificity(self):
        return self.sub_selector.specificity

    def __repr__(self):
        return ':not(%r)' % self.sub_selector
