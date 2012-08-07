# coding: utf8

import re
import os.path
from setuptools import setup


ROOT = os.path.dirname(__file__)
README = open(os.path.join(ROOT, 'README.rst')).read()
INIT_PY = open(os.path.join(ROOT, 'lselect', '__init__.py')).read()
VERSION = re.search("VERSION = '([^']+)'", INIT_PY).group(1)


setup(
    name='lselect',
    version=VERSION,
    author='Simon Sapin',
    author_email='simon.sapin@exyr.org',
    description='CSS selectors for lxml.',
    long_description=README,
    url='http://packages.python.org/lselect/',
    license='BSD',
    packages=['lselect'],
    install_requires=['cssselect', 'tinycss', 'lxml']
)
