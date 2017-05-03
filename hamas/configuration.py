#!/usr/bin/os.environ python
# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    02.05.2017
#   LICENSE:    MIT
#   FILE:       config.py
# =============================================================================
"""Definition of global configuration variables.
"""

import configparser
import os


def load_config():
    global HAMASRC, MACHINE_NAME, USE_ZIGBEE, USE_MQTT, USE_UDS, LOGRC, DEVICE
    conf_file = os.environ[
        'HAMAS_CONFIG'] if 'HAMAS_CONFIG' in os.environ.keys(
    ) else os.path.abspath(os.path.join(os.path.dirname(__file__),
                        '../configuration/hamas.conf'))

    HAMASRC = os.path.abspath(conf_file)
    conf_dir = os.path.dirname(HAMASRC)

    config = configparser.ConfigParser()
    config.read(HAMASRC)

    LOGRC = os.path.abspath(
        os.path.join(conf_dir, config['General']['log_config']))

    MACHINE_NAME = config['General']['machine_name']
    USE_ZIGBEE = config.getboolean('General', 'use_zigbee')
    USE_ZIGBEE = USE_ZIGBEE and not ('HAMASNOZIGBEE' in os.environ.keys() and
                                     os.environ['HAMASNOZIGBEE'] == '1')
    USE_MQTT = config.getboolean('General', 'use_mqtt')
    USE_UDS = config.getboolean('General', 'use_uds')
    USE_UDS = USE_UDS and os.name == 'posix'
    if USE_ZIGBEE:
        DEVICE = config['ZigBee']['device']


HAMASRC = ''
MACHINE_NAME = ''
USE_ZIGBEE = ''
USE_MQTT = ''
USE_UDS = ''
LOGRC = ''
DEVICE = ''

load_config()
