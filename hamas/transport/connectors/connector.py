# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    06.10.2016
#   LICENSE:    MIT
#   FILE:	connector.py
# =============================================================================
"""Abstract base class for connectors.
"""

import abc


class Connector(abc.ABC):
    """Base Class for connectors"""

    def __init__(self):
        """TODO: to be defined1. """
        super(Connector, self).__init__()

    def __repr__(self):
        return '{} on {}'.format(self.__class__.__name__, self.address)

    @abc.abstractmethod
    def __contains__(self, platform_url):
        pass

    @property
    @abc.abstractmethod
    def address(self):
        pass

    @property
    @abc.abstractmethod
    def other_platforms(self):
        pass

    @abc.abstractmethod
    def unicast(self, platform_name, message):
        pass

    @abc.abstractmethod
    def broadcast(self, message):
        pass
