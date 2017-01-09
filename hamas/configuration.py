# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    05.10.2016
#   LICENSE:    MIT
#   FILE:	configuration.py
# =============================================================================
"""Configuration loader
"""

import configparser
import os.path

from .exceptions import ConfigError


class Configuration(object):
    def __init__(self, conf_file=None):
        self.parser = configparser.ConfigParser()
        self.parser.optionxform = str
        self.default_conf_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../configuration/default.conf'))
        self.conf_file = os.path.normpath(conf_file) if conf_file is not None else self.default_conf_file

    def __eq__(self, other):
        self.update()
        other.update()

        equal = self.parser.sections() == other.parser.sections()

        if equal:
            for section in self.parser.sections():
                equal &= sorted(self.parser.items(section)) == sorted(
                    other.parser.items(section))

        return equal

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "{}: [".format(self.conf_file) + "], [".join(str.format(s) for s in self.parser.sections()) + "]"

    def reset_config(self):
        """Resets the config conf_file to working state
        """
        self.parser.read(self.default_conf_file)
        with open(self.conf_file, 'w') as conf:
            self.parser.write(conf)

    def update(self):
        if not os.path.isfile(self.conf_file):
            raise FileNotFoundError('The file {} cannot be not found.'.format(
                self.conf_file))
        self.parser.read(self.conf_file)

    def get_parameter(self, section, parameter):
        """Function to request a setting from the configuration file
        Attributes:
            section(str):The name of the requested settings section
            parameter(str):The name of the requested parameter
        Returns:
            The value of the setting
        """
        self.update()
        if section in self.parser.sections():
            if parameter in self.parser[section]:
                return self.parser[section][parameter]
            else:
                raise ConfigError(
                    "The parameter {} in the '{}' section was not found in "
                    "the config file {}."
                    "".format(
                        section, parameter, self.conf_file))
        else:
            raise ConfigError(
                "The section '{}' was not found in the config file {}.".format(
                    section, self.conf_file))
