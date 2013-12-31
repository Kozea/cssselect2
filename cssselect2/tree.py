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


class Element(object):
    def __init__(self, etree_element, parent=None,
                 index=None, previous=None):
        self.etree_element = etree_element
        self.get_attr = etree_element.get
        self.parent = parent
        self.index = index
        self.previous = previous

    def iter_ancestors(self):
        element = self
        while element.parent is not None:
            element = element.parent
            yield element

    def iter_previous_siblings(self):
        element = self
        while element.previous is not None:
            element = element.previous
            yield element

    def iter_children(self):
        child = None
        for i, etree_child in enumerate(self.etree_children):
            child = type(self)(
                etree_child,
                parent=self,
                index=i,
                previous=child,
            )
            yield child

    @cached_property
    def etree_children(self):
        return [c for c in self.etree_element if isinstance(c.tag, basestring)]

    @cached_property
    def local_name(self):
        namespace_url, local_name = _split_etree_tag(self.etree_element.tag)
        self.__dict__['namespace_url'] = namespace_url
        return local_name

    @cached_property
    def namespace_url(self):
        namespace_url, local_name = _split_etree_tag(self.etree_element.tag)
        self.__dict__['local_name'] = local_name
        return namespace_url

    @cached_property
    def id(self):
        # TODO: make the attribute name configurable?
        return self.get_attr('id')

    @cached_property
    def classes(self):
        # TODO: make the attribute name configurable?
        return set(split_whitespace(self.get_attr('class', '')))

    @cached_property
    def lang(self):
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
