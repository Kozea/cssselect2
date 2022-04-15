First Steps
===========

.. currentmodule:: cssselect2


Installation
------------

The easiest way to use tinycss2 is to install it in a Python `virtual
environment`_. When your virtual environment is activated, you can then install
cssselect2 with pip_::

    pip install cssselect2

This will also automatically install tinycss2’s only dependencies, tinycss2_
and webencodings_.  cssselect2, tinycss2 and webencodings only contain Python
code and should work on any Python implementation.

cssselect2 also is packaged for many Linux distributions (Debian, Ubuntu,
Fedora, Archlinux, Gentoo…).

.. _virtual environment: https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/
.. _pip: https://pip.pypa.io/
.. _webencodings: https://pythonhosted.org/webencodings/
.. _tinycss2: https://doc.courtbouillon.org/tinycss2/


Basic Example
-------------

Here is a classical cssselect2 workflow:

- parse a CSS stylesheet using tinycss2_,
- store the CSS rules in a :class:`Matcher` object,
- parse an HTML document using an ElementTree-like parser,
- wrap the HTML tree in a :class:`ElementWrapper` object,
- find the CSS rules matching each HTML tag, using the matcher and the wrapper.

.. literalinclude:: example.py
