Changelog
---------


Version 0.8.0
.............

Released on 2025-03-05.

* Drop support of Python 3.8 and 3.9, support 3.12 and 3.13
* Handle case-sensitive and case-insensitive attribute selectors


Version 0.7.0
.............

Released on 2022-09-19.

* Support :has selector


Version 0.6.0
.............

Released on 2022-04-15.

**This version deprecates the ``iter_ancestors`` and ``iter_previous_siblings``
methods, that will be removed in 0.7.0. Use the ``ancestors`` and
``previous_siblings`` properties instead.**

* Improve speed of ancestors and previous siblings


Version 0.5.0
.............

Released on 2022-02-27.

* Support Python 3.10
* Drop support of Python 3.6
* Handle many CSS4 selectors
* Ignore comments at the beginning of selectors


Version 0.4.1
.............

Released on 2020-10-29.

* Fix PyPI description and various links.


Version 0.4.0
.............

Released on 2020-10-29.

* Drop support of Python 3.5, add support of Python 3.9.
* Don’t crash on empty :not() selectors.
* New code structure, new packaging, new documentation.


Version 0.3.0
.............

Released on 2020-03-16.

* Drop Python2 support.
* Improve packaging and testing.


Version 0.2.2
.............

Released on 2019-09-06.

* Optimize lang attribute selectors.


Version 0.2.1
.............

Released on 2017-10-02.

* Fix documentation.


Version 0.2.0
.............

Released on 2017-08-16.

* Fix some selectors for HTML documents with no namespace.
* Don't crash when the attribute comparator is unknown.
* Don't crash when there are empty attribute classes.
* Follow semantic versioning.


Version 0.1
...........

Released on 2017-07-07.

* Initial release.
