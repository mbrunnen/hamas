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
    conf_file = os.environ[
        'HAMAS_CONFIG'] if 'HAMAS_CONFIG' in os.environ.keys(
    ) else '../configuration/hamas.conf'
    conf_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), conf_file))
    conf_dir = os.path.abspath(os.path.dirname(conf_path))

    config = configparser.ConfigParser()
    config.read(conf_path)

    log_conf_path = os.path.abspath(
        os.path.join(conf_dir, config['General']['log_config']))

    use_uds = os.name == 'posix' and (
        config.getboolean('General', 'use_uds') or
        ('HAMASUDS' in os.environ.keys() and os.environ['HAMASUDS'] == '1'))

    return conf_path, log_conf_path, use_uds


HAMASRC, LOGRC, USE_UDS = load_config()
