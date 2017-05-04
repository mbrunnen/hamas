# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR: Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    05.10.2016
#   LICENSE:    MIT
#   FILE:   test_configuration.py
# =============================================================================

import os
from os.path import abspath, join, dirname

import pytest

from hamas.configuration import default_config, Configuration


class TestConfiguration:
    def test_default_config(self):
        assert default_config.file == abspath(
            join(dirname(__file__), '../configuration/hamas.conf'))
        assert default_config.machine_name == 'local'
        assert default_config.use_zigbee is True
        assert default_config.use_mqtt is True
        assert default_config.use_uds is False
        assert default_config.log_conf == abspath(
            join(dirname(__file__), '../configuration/logging.yaml'))
        assert default_config.device == '/dev/ttyUSB'

    @pytest.mark.parametrize(
        'conf_file, machine_name, use_zigbee, use_mqtt, use_uds, logrc, device',
        [('./test_configurations/test_1.conf', 'local', True, True, True,
          './test_configurations/logging.yaml', '/dev/foo'),
         ('./test_configurations/test_2.conf', 'emasem01', False, False, False,
          './test_configurations/logging.yaml', '')])
    def test_file(self, conf_file, machine_name, use_zigbee, use_mqtt, use_uds,
                  logrc, device):
        conf = Configuration(conf_file)

        assert conf.file == abspath(join(dirname(__file__), conf_file))
        assert conf.machine_name == machine_name
        assert conf.use_zigbee == use_zigbee
        assert conf.use_mqtt == use_mqtt
        assert conf.use_uds == use_uds and os.name == 'posix'
        assert conf.log_conf == abspath(join(dirname(__file__), logrc))
        assert conf.device == device
