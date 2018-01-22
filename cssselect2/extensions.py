# coding: utf8

import re

from tinycss2 import serialize

from . import extensions as ex


def _match(selector):
    "Callback for match pseudoClass."
    regex = serialize(selector.arguments)
    trim = '\"\''
    if regex[0] in trim and regex[0] == regex[-1]:
        regex = regex[1:-1]
    return ('(re.search("%s", ex.textstring(el)) is not None)' % regex)


def textstring(el):
    """Return a text string of all text for subtree of el."""
    strval = u''
    strval += (el.etree_element.text or u'')
    for elem in el.iter_children():
            strval += elem.textstring()
    strval += (el.etree_element.tail or u'')
    return strval


extensions = {'pseudoClass': {'match': {'callback': _match,
                                        'modules': {'re': re,
                                                    'ex': ex}
                                        },
                              'pass': {'callback': lambda s: '1'},
                              'deferred': {'callback': lambda s: '1'},
                              }
              }
