#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from setuptools import setup

if sys.version_info < (2, 7):
    raise SystemExit("*** Requires python >= 2.7.0")

with open('README.rst') as doc:
    long_description = doc.read()
with open('CHANGES.rst') as changes:
    long_description += changes.read()

with open('requirements.txt') as reqs:
    requirements = [n.strip('\n') for n in reqs]

setup(
    name='cdifflint',
    version='1.0.0',
    author='Rory Geoghegan',
    author_email='r.geoghegan(@)gmail(.)com',
    license='BSD-3',
    description='View colored, incremental diff in a workspace, annotated '
    'with messages from your favorite linter.',
    long_description=long_description,
    keywords='colored incremental side-by-side diff, with lint messages',
    url='https://github.com/rgeoghegan/cdifflint',
    install_requires=requirements,
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Topic :: Utilities',
        'License :: OSI Approved :: BSD License',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    py_modules=['cdifflint'],
    scripts=['cdifflint'],
)

# vim:set et sts=4 sw=4 tw=79:
