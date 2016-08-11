# coding: utf8

from tinycss2 import serialize
import re


def _match(selector):
    "Callback for match pseudoClass."
    regex = serialize(selector.arguments)
    trim = '\"\''
    if regex[0] in trim and regex[0] == regex[-1]:
      regex = regex[1:-1]
    return ('(re.search("%s", el.textstring()) is not None)' % regex)

extensions = {'pseudoClass': {'match': {'callback': _match,
                                        'modules': {'re': re}
                                        },
                              'pass': {'callback': lambda s: '1'},
                              'deferred': {'callback': lambda s: '1'},
                              }
              }
