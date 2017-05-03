# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR: Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    05.10.2016
#   LICENSE:    MIT
#   FILE:   test_configuration.py
# =============================================================================

import os
from importlib import reload
from os.path import abspath, join, dirname

import pytest

import hamas.configuration
from hamas import HAMASRC, MACHINE_NAME, USE_ZIGBEE, USE_MQTT, USE_UDS, LOGRC, DEVICE


class TestConfiguration:
    def test_default_file(self):
        assert HAMASRC == abspath(
            join(dirname(__file__), '../configuration/hamas.conf'))
        assert MACHINE_NAME == 'local'
        assert USE_ZIGBEE is True
        assert USE_MQTT is True
        assert USE_UDS is False
        assert LOGRC == abspath(
            join(dirname(__file__), '../configuration/logging.yaml'))
        assert DEVICE == '/dev/ttyUSB'

    @pytest.mark.parametrize(
        'conf_file, machine_name, use_zigbee, use_mqtt, use_uds, logrc, device',
        [('./test_configurations/test_1.conf', 'local', True, True, True,
          './test_configurations/logging.yaml', '/dev/foo'),
         ('./test_configurations/test_2.conf', 'emasem01', False, False, False,
          './test_configurations/logging.yaml', '')])
    def test_file(self, conf_file, machine_name, use_zigbee, use_mqtt, use_uds,
                  logrc, device):
        os.environ['HAMAS_CONFIG'] = join(dirname(__file__), conf_file)
        conf = reload(hamas.configuration)

        assert conf.HAMASRC == abspath(join(dirname(__file__), conf_file))
        assert conf.MACHINE_NAME == machine_name
        assert conf.USE_ZIGBEE == use_zigbee
        assert conf.USE_MQTT == use_mqtt
        assert conf.USE_UDS == use_uds and os.name == 'posix'
        assert conf.LOGRC == abspath(join(dirname(__file__), logrc))
        assert conf.DEVICE == device
