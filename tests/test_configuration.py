# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    05.10.2016
#   LICENSE:    MIT
#   FILE:	test_configuration.py
# =============================================================================
"""Test the configuration loader
"""
from os.path import abspath

import pytest

from hamas import Configuration, ConfigError


class TestConfiguration:
    def test_no_file(self):
        conf = Configuration('no file')
        with pytest.raises(FileNotFoundError):
            conf.update()
        conf = Configuration('./test_configurations')
        with pytest.raises(FileNotFoundError):
            conf.update()

    def test_compare(self):
        conf_1 = Configuration('./tests/test_configurations/test_eq_1.conf')
        conf_2 = Configuration('./tests/test_configurations/test_eq_2.conf')
        conf_3 = Configuration('./tests/test_configurations/test_eq_3.conf')
        assert conf_1 == conf_2
        assert conf_2 != conf_3
        assert conf_1 != conf_3

        with open(abspath('./tests/test_configurations/test_eq_1.conf')) as file_1:
            str_1 = file_1.read()
        with open(abspath('./tests/test_configurations/test_eq_2.conf')) as file_2:
            str_2 = file_2.read()
        assert str_1 != str_2

    def test_reset(self, tmpfile):
        reference = Configuration('./configuration/default.conf')
        conf = Configuration(tmpfile.name)

        assert reference != conf
        conf.reset_config()
        assert reference == conf

    def test_get_param(self):
        config = Configuration('./tests/test_configurations/test.conf')
        with pytest.raises(ConfigError):
            config.get_parameter('Test Section', 'spam')
        with pytest.raises(ConfigError):
            config.get_parameter('spam', 'test_parameter_1')
        assert 'test value' == config.get_parameter('Test Section',
                                                    'test_parameter_1')
        assert '-3' == config.get_parameter('Test Section', 'test_parameter_2')
        assert '.5' == config.get_parameter('Test Section', 'test_parameter_3')
        assert '.5' == config.get_parameter('Test Section', 'test_parameter_3')
        assert 'test' == config.get_parameter('Another Test Section',
                                              'test_param')
