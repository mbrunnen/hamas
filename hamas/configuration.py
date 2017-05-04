#!/usr/bin/os.environ python
# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    02.05.2017
#   LICENSE:    MIT
#   FILE:       config.py
# =============================================================================
"""This package is configured through a special configuration file, usually
located in `configuration/hamas.conf`. The user can set the environment
variable :envvar:`HAMAS_CONFIG` to define the location of the configuration
file.

The file is formatted as defined in :mod:`configparser`. It consists of one
general section and a ZigBee specific section.  The general section contains
information about the machine name, the location of the logging configuration
file and which communication protocols shall be used. In the ZigBee section is
defined on which port the ZigBee module is connected to the machine.

.. envvar:: HAMAS_CONFIG

If the :envvar:`HAMAS_CONFIG` environment variable is set, the file specified
in the variable will be used instead of the default one. On a Linux system
the environment variable is set as follows:

.. code-block:: sh

    export set HAMAS_CONFIG=~/.my_hamas.conf

Example:
    A configuration file can look like this:

    .. code-block:: ini

        ; A exemplary configuration file
        [General]
        machine_name = local
        use_zigbee = true
        use_mqtt = true
        use_uds = false
        log_config = ./logging.yaml

        [ZigBee]
        device = /dev/ttyUSB
        ; vim:ft=dosini

"""

import configparser
import logging
import os

log = logging.getLogger(__name__)


class Configuration(object):
    """The :class:`Configuration` class parses the configuration file and
    contains the retrieved information. The :meth:`AgentManager.create` accept
    a instance of this class and will build the multi-agent system according
    to the given configuration. When importing the :mod:`hamas` package, a
    default configuration will be created: :data:`def_config`. This default
    configuration is either created from the default configuratin file or the
    one given by :envvar:`HAMAS_CONFIG`. This default configuration will be
    used by the :meth:`AgentManager.create`

    """

    def __init__(self, conf_file):
        super(Configuration, self).__init__()

        conf_file = conf_file
        self._file = os.path.abspath(conf_file)
        conf_dir = os.path.dirname(self._file)

        config = configparser.ConfigParser()
        config.read(self._file)

        self._log_conf = os.path.abspath(
            os.path.join(conf_dir, config['General']['log_config']))

        self._machine_name = config['General']['machine_name']
        self._use_zigbee = config.getboolean('General', 'use_zigbee')
        self._use_mqtt = config.getboolean('General', 'use_mqtt')
        self._use_uds = config.getboolean('General', 'use_uds')
        if 'ZigBee' in config and 'device' in config['ZigBee']:
            self._device = config['ZigBee']['device']
        else:
            self._device = ''

    @property
    def file(self):
        """str: Returns the path of the configuration file.
        """
        return self._file

    @property
    def log_conf(self):
        """str: Returns the path of the log configuration file.
        """
        return self._log_conf

    @property
    def machine_name(self):
        """str: Returns the machine name specified in the configuration file.
        """
        return self._machine_name

    @property
    def use_zigbee(self):
        """bool: Returns if ZigBee shall be used for communication.
        """
        return self._use_zigbee

    @property
    def use_mqtt(self):
        """bool: Returns if MQTT shall be used for communication.
        """
        return self._use_mqtt

    @property
    def use_uds(self):
        """bool: Returns if the Unix Domain Socket shall be used for communication.
        """
        return self._use_uds

    @property
    def device(self):
        """str: Returns the file descriptor of connected ZigBee hardware.
        """
        return self._device


def_conf_file = os.environ[
    'HAMAS_CONFIG'] if 'HAMAS_CONFIG' in os.environ.keys() else os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../configuration/hamas.conf'))

def_config = Configuration(def_conf_file)
