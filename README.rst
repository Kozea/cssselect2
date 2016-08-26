cssselect2: unmaintained and incomplete experiments with CSS selectors for Python
=================================================================================

`cssselect`_ implements `CSS Selectors`_ by converting them to XPath_,
and then relying on lxml_’s XPath implementation.

At first, converting simple selectors seems easy enough.
But the two languages are different enough that I’m not even convinced that
some more complex selectors even have a correct translation.
See `issue 12`_ for an example.

As such, I believe the XPath approach is fundamentally flawed.
So I started in this repository to implement Selectors without XPath,
by traversing a document tree directly.
It mostly works, but I got stuck on `deciding what kind of tree to support`_.

Since then, I’ve moved on to other things and I’m not very interested in pushing this further.
Please consider this project abandonned.
I will not publish it on PyPI or accept contributions.

Feel free to use the code per the license if you find it useful.
If you make a proper library out of it I’m willing to give away the `cssselect2` name on PyPI
(file an issue on this repository to let me know).

.. _cssselect: https://github.com/scrapy/cssselect
.. _CSS Selectors: https://drafts.csswg.org/selectors/
.. _XPath: http://www.w3.org/TR/xpath/
.. _lxml: http://lxml.de/
.. _issue 12: https://github.com/scrapy/cssselect/issues/12
.. _deciding what kind of tree to support: https://github.com/SimonSapin/cssselect2/issues/1
