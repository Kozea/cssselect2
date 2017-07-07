#!/usr/bin/env python
# coding: utf8

import os.path
import re
import sys

from setuptools import setup

ROOT = os.path.dirname(__file__)
README = open(os.path.join(ROOT, 'README.rst')).read()
INIT_PY = open(os.path.join(ROOT, 'cssselect2', '__init__.py')).read()
VERSION = re.search("VERSION = '([^']+)'", INIT_PY).group(1)

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

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
    package_data={'cssselect2': ['tests/*']},
    install_requires=['tinycss2'],
    setup_requires=pytest_runner,
    test_suite='cssselect2.tests',
    tests_require=[
        'pytest-runner', 'pytest-cov', 'pytest-flake8', 'pytest-isort'],
    extras_require={'test': [
        'pytest-runner', 'pytest-cov', 'pytest-flake8', 'pytest-isort']},
)
