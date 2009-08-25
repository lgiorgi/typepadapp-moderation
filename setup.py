#!/usr/bin/env python
from setuptools import setup, find_packages
setup(
    name='moderation',
    version='1.1',
    description='Moderation panel for Motion.',
    author='Six Apart',
    author_email='python@sixapart.com',
    url='http://github.com/sixapart/moderation/',

    packages=find_packages(),
    provides=['moderation'],
    include_package_data=True,
    zip_safe=False,
    requires=['Django(>=1.0.2)', 'motion'],
)