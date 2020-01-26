.. include:: ../README.rst


Installation
============

Installing cssselect2 with pip_ should Just Work::

    pip install cssselect2

This will also automatically install cssselect2’s only dependency, tinycss2_.
cssselect2 and tinycss2 both only contain Python code and should work on any
Python implementation, although they’re only tested on CPython.

.. _pip: http://pip-installer.org/
.. _tinycss2: http://tinycss2.readthedocs.io/


Basic Example
=============

Here is a classical cssselect2 workflow:

- parse a CSS stylesheet using tinycss2_,
- store the CSS rules in a :meth:`~cssselect2.Matcher` object,
- parse an HTML document using an ElementTree-like parser,
- wrap the HTML tree in a :meth:`~cssselect2.ElementWrapper` object,
- find the CSS rules matching each HTML tag, using the matcher and the wrapper.

.. literalinclude:: example.py

.. module:: cssselect2
.. autoclass:: Matcher
   :members:
.. autofunction:: compile_selector_list
.. autoclass:: ElementWrapper
   :members:
.. autoclass:: SelectorError


.. include:: ../CHANGES
