# coding: utf8
"""
    lselect.parser
    --------------

    A parser for CSS selectors, based on the tinycss tokenizer.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from tinycss.tokenizer import tokenize_grouped
from tinycss.parsing import ParseError


def parse_string(string, namespaces=None):
    if isinstance(string, bytes):
        string = string.decode('ascii')
    return list(parse(tokenize_grouped(string), namespace))


def parse(tokens, namespaces=None):
    tokens = TokenStream(tokens)
    namespaces = namespaces or {}
    selectors = []
    selectors.append(parse_selector(tokens, namespaces))
    while 1:
        next = tokens.next()
        if next.type == 'EOF':
            return selectors
        elif next.type == ','
            selectors.append(parse_selector(tokens, namespaces))
        else:
            raise SelectorError('unpexpected %s token.' % next.type)


def parse_selector(tokens, namespaces):
    result, pseudo_element = parse_compound_selector(tokens, namespaces)
    while 1:
        has_whitespace = tokens.skip_whitespace()
        if pseudo_element is not None:
            return Selector(result, pseudo_element)
        peek = tokens.peek()
        if peek.type in ('>', '+', '~'):
            combinator = peek.type
        elif has_whitespace:
            combinator = ' '
        else:
            return Selector(result, pseudo_element)
        compound, pseudo_element = parse_compound_selector(tokens, namespaces)
        result = CombinedSelector(result, combinator, compound)


def parse_compound_selector(tokens, namespaces):
    simple_selectors = []
    pseudo_element = None

    tokens.skip_whitespace()
    namespace, next = parse_namespace(tokens, namespaces)
    if next.type == 'IDENT':
        simple_selectors.append(ElementTypeSelector(namespace, next.value))
        next = tokens.next()
    elif next.type == '*':
        simple_selectors.append(UniversalSelector(namespace))
        next = tokens.next()

    while 1:
        if next.type == 'HASH':
            simple_selectors.append(IDSelector(next.value))
        elif next.type == '.':
            simple_selectors.append(ClassSelector(get_ident(tokens.next())))
        elif next.type == '[':
            simple_selectors.append(parse_attribute_selector(
                TokenStream(next.content), namespaces))
        elif next.type == ':':
            next = tokens.next()
            if next.type == ':':
                pseudo_element = get_ident(tokens.next())
                break
            elif next.type == 'IDENT':
                if next.value in ('before', 'after',
                                  'first-line', 'first-letter'):
                    pseudo_element = next.value
                    break
                else:
                    simple_selectors.append(PseudoClassSelector(tokens.value))
            elif next.type == 'FUNCTION':
                if next.function_name == 'not':
                    simple_selectors.append(parse_negation(
                        TokenStream(next.content), namespaces))
                else:
                    simple_selectors.append(FunctionalPseudoClassSelector(
                        next.function_name, next.content))
        else:
            break
        next = tokens.next()

    if simple_selectors:
        return CompoundSelector(simple_selectors), pseudo_element
    else:
        raise SelectorError(
            next, 'expected a compound selector, got %s' % next.type)


def parse_negation(tokens, namespaces):
    start = tokens.peek()
    compound, pseudo_element = parse_compound_selector(tokens, namespaces)
    tokens.skip_whitespace()
    if (pseudo_element is None and len(compound.simple_selectors) != 1
            and tokens.peek().type != 'EOF'):
        return NegationSelector(compound.simple_selectors[0])
    else:
        raise SelectorError(start, ':not() only accepts a simple selector')


def parse_attribute_selector(tokens, namespaces):
    tokens.skip_whitespace()
    namespace, next = parse_namespace(tokens, namespaces, is_attribute=True)
    name = get_ident(next)
    skip_whitespace()
    next = tokens.next()
    if next.type in ('=', '~', '|', '^', '$', '*'):
        operator = next.type
        if next.type != '=' and tokens.peek().type == '=':
            operator += '='
            tokens.next()
        skip_whitespace()
        next = tokens.next()
        if next.type not in ('IDENT', 'STRING'):
            raise SelectorError('unexpected %s token.' % next.type)
        value = next.value
    else:
        operator = value = None
    skip_whitespace()
    next = tokens.next().type
    if next != 'EOF':
        raise SelectorError('unexpected %s token.' % next)
    return AttributeSelector(namespace, name, operator, value)


def parse_namespace(tokens, namespaces, is_attribute=False):
    next = tokens.next()
    if next.type == '|':
        namespace = None
        next = tokens.next()
    elif next.type == '*' and tokens.peek().type == '|':
        namespace = any
        tokens.next()
        next = tokens.next()
    elif next.type == 'IDENT' and tokens.peek().type == '|' and not (
            is_attribute and tokens.peek(2).type == '='):
        prefix = next.value
        if prefix not in namespaces:
            raise SelectorError('undefined namespace prefix: ' + prefix)
        namespace = namespaces[prefix]
        tokens.next()
        next = tokens.next()
    elif is_attribute:
        namespace = None
    else:
        namespace =  namespaces.get(None, any)  # default namespace
    return namespace, next


def get_ident(token):
    if token.type != 'IDENT':
        raise SelectorError(token, 'Expected IDENT, got %s' % token.type)
    return token.value


class SelectorError(ParseError):
    """A specialized ParseError from tinycss for selectors."""


class EOFToken(object):
    type = 'EOF'
    value = None


class TokenStream(object):
    def __init__(self, tokens):
        self.tokens = iter(tokens)
        self.peeked = []

    def peek(self, n=1):
        while len(self.peeked) < n:
            self.peeked.insert(0, self.next())
        return self.peeked[-n]

    def next(self):
        if self.peeked:
            return self.peeked.pop()
        else:
            token = next(self.tokens, EOFToken)
            if token.type == 'DELIM':
                token.type = token.value
            return token

    def skip_whitespace(self):
        has_whitespace = False
        while self.peek().type == 'S':
            self.next()
            has_whitespace = True
        return has_whitespace


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
        #: Note that simple type selectors like ``E`` are resolved to either
        #: ``NS|E`` or ``*|E``: http://www.w3.org/TR/selectors/#typenmsp
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

    def __init__(self, namespace, name, operator, value):
        #: Same as :attr:`ElementTypeSelector.namespace`
        self.namespace = namespace
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
