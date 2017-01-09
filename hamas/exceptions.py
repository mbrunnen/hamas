# -*- coding: utf-8 -*-
# ==============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    05.08.2016
#   LICENSE:    MIT
#   FILE:       exceptions.py
# ==============================================================================
"""Exception used by hamas
"""


class HamasError(Exception):
    """Base Class for all exceptions defined by hamas
    """
    def __init__(self, *args, **kwargs):
        super(HamasError, self).__init__(*args, **kwargs)
        self.message = args[0] if len(args) > 0 else None


class AgentError(HamasError):
    """Raised if an agent fails
    """
    pass


class TransmissionError(HamasError):
    """Raised if a transmission over the air or cable fails
    """
    pass


class PortError(HamasError):
    """Raised, when a port is not ready to communicate.
    """
    pass


class ConnectorError(FileNotFoundError, HamasError):
    """Raised when a connector is not responding.
    """
    pass


class MarketError(HamasError):
    """Raised on market specific errors
    """
    pass


class DeviceHandlerError(HamasError):
    """Raised on device handler specific errors
    """
    pass


class ConfigError(KeyError, HamasError):
    """Raised when there is a problem with the config conf_file.
    """
    pass
