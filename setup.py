# coding: utf8

import re
import os.path
from setuptools import setup


ROOT = os.path.dirname(__file__)
README = open(os.path.join(ROOT, 'README.rst')).read()
INIT_PY = open(os.path.join(ROOT, 'cssselect2', '__init__.py')).read()
VERSION = re.search("VERSION = '([^']+)'", INIT_PY).group(1)


setup(
    name='cssselect2',
    version=VERSION,
    author='Simon Sapin',
    author_email='simon.sapin@exyr.org',
    description='CSS selectors for Python ElementTree',
    long_description=README,
    url='http://packages.python.org/cssselect2/',
    license='BSD',
    packages=['cssselect2'],
    install_requires=['tinycss2'],
)
