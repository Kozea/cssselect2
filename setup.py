#!/usr/bin/env python

import sys

from setuptools import setup

if sys.version_info.major < 3:
    raise RuntimeError(
        'cssselect2 does not support Python 2.x anymore. '
        'Please use Python 3 or install an older version of cssselect2.')

setup()
