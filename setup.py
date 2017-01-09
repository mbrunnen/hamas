# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    14.07.2016
#   LICENSE:    MIT
#   FILE:       setup.py
# =============================================================================
"""Install the package hamas with python -m setup.py install
"""

from setuptools import setup, find_packages

setup(
    name='hamas',
    version='0.0.1',
    description='Description',
    url='Upstream URL',
    author='Manoel Brunnen (@mbrunnen)',
    author_email='manoel.brunnen@gmail.com',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'numpy',
        'xbee',
        'pyserial',
        'pyyaml',
        'Sphinx',
        'sphinxcontrib-asyncio',
    ],
    tests_require=[
        'pytest',
        'pytest-asyncio',
    ],
)
