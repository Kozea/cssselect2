# coding: utf8

from __future__ import unicode_literals

import re

from ._compat import basestring


class cached_property(object):
    # Borrowed from Werkzeug
    # https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/utils.py

    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None, __missing=object()):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, __missing)
        if value is __missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value


class ElementWrapper(object):
    """
    A wrapper for an ElementTree :class:`~xml.etree.ElementTree.Element`
    for Selector matching.

    This class should not be instanciated directly.
    :meth:`from_root` should be used for the root element of a document,
    and other elements should be accessed (and wrappers generated)
    using methods such as :meth:`iter_children` and :meth:`iter_subtree`.

    """
    @classmethod
    def from_root(cls, root):
        """
        :param root:
            An ElementTree :class:`~xml.etree.ElementTree.Element`
            for the root element of a document.
            If the given element is not the root,
            selector matching will be `scope-contained`_
            to the subtree rooted at that element.
        :returns:
            A new :class:`ElementWrapper`

        .. _scope-contained: http://dev.w3.org/csswg/selectors4/#scope-contained-selectors

        """
        return cls(root, parent=None, index=None, previous=None)

    def __init__(self, etree_element, parent, index, previous):
        #: The underlying ElementTree :class:`~xml.etree.ElementTree.Element`
        self.etree_element = etree_element
        #: The parent :class:`ElementWrapper`,
        #: or :obj:`None` for the root element.
        self.parent = parent
        #: The position within the :attr:`parent`’s children (starts at 0),
        #: or :obj:`None` for the root element.
        self.index = index
        #: The previous sibling :class:`ElementWrapper`,
        #: or :obj:`None` for the root element.
        self.previous = previous

        # See the get_attr method below.
        self.get_attr = etree_element.get

    def iter_ancestors(self):
        """Return an iterator of existing :class:`ElementWrapper` objects
        for this element’s ancestors,
        in reversed tree order (from :attr:`parent` to the root)

        The element itself is not included,
        this is an empty sequence for the root element.

        """
        element = self
        while element.parent is not None:
            element = element.parent
            yield element

    def iter_previous_siblings(self):
        """Return an iterator of existing :class:`ElementWrapper` objects
        for this element’s previous siblings,
        in reversed tree order.

        The element itself is not included,
        this is an empty sequence for a first child or the root element.

        """
        element = self
        while element.previous is not None:
            element = element.previous
            yield element

    def iter_children(self):
        """Return an iterator of newly-created :class:`ElementWrapper` objects
        for this element’s child elements,
        in tree order.

        """
        child = None
        for i, etree_child in enumerate(self.etree_children):
            child = type(self)(
                etree_child,
                parent=self,
                index=i,
                previous=child,
            )
            yield child

    def iter_subtree(self):
        """Return an iterator of newly-created :class:`ElementWrapper` objects
        for the entire subtree rooted at this element,
        in tree order.

        Unlike in other methods, the element itself *is* included.

        This loops over an entire document:

        .. code-block:: python

            for element in ElementWrapper.from_root(root_etree_element).iter():
                ...

        """
        stack = [iter([self])]
        while stack:
            element = next(stack[-1], None)
            if element is None:
                stack.pop()
            else:
                yield element
                stack.append(element.iter_children())

    @cached_property
    def etree_children(self):
        """This element’s children,
        as a list of ElementTree :class:`~xml.etree.ElementTree.Element`.

        Other ElementTree nodes such as
        :class:`comments <~xml.etree.ElementTree.Comment>` and
        :class:`processing instructions
        <~xml.etree.ElementTree.ProcessingInstruction>`
        are not included.

        """
        return [c for c in self.etree_element if isinstance(c.tag, basestring)]

    @cached_property
    def local_name(self):
        """The local name of this element, as a string."""
        namespace_url, local_name = _split_etree_tag(self.etree_element.tag)
        self.__dict__['namespace_url'] = namespace_url
        return local_name

    @cached_property
    def namespace_url(self):
        """The namespace URL of this element, as a string."""
        namespace_url, local_name = _split_etree_tag(self.etree_element.tag)
        self.__dict__['local_name'] = local_name
        return namespace_url

    # On instances, this is overridden by an instance attribute
    # that *is* the bound `get` method of the ElementTree element.
    # This avoids the runtime cost of a function call.
    def get_attr(self, name, default=None):
        """
        Return the value of an attribute.

        :param name:
            The name of the attribute as a string in ElementTree’s notation:
            the local name for attributes not in any namespace,
            ``"{namespace url}local name"`` for other attributes.
        :returns:
            The value as a string,
            or :obj:`default` if the element does not have this attribute.

        Note: this just calls ElementTree’s
        :meth:`~xml.etree.ElementTree.Element.get` method.

        """
        return self.etree_element.get(name, default)

    @cached_property
    def id(self):
        """The ID of this element, as a string."""
        # TODO: make the attribute name configurable?
        return self.get_attr('id')

    @cached_property
    def classes(self):
        """The classes of this element, as a :class:`set` of strings."""
        # TODO: make the attribute name configurable?
        return set(split_whitespace(self.get_attr('class', '')))

    @cached_property
    def lang(self):
        """The language of this element, as a string."""
        xml_lang = self.get_attr('{http://www.w3.org/XML/1998/namespace}lang')
        if xml_lang is not None:
            return xml_lang
        # TODO: make the attribute name configurable?
        lang = self.get_attr('lang')
        if lang is not None:
            return lang
        if self.parent is not None:
            return self.parent.lang


# http://dev.w3.org/csswg/selectors/#whitespace
split_whitespace = re.compile('[^ \t\r\n\f]+').findall


def _split_etree_tag(tag):
    pos = tag.rfind('}')
    if pos == -1:
        return '', tag
    else:
        assert tag[0] == '{'
        return tag[1:pos], tag[pos + 1:]
