# -*- coding: utf-8 -*-
import logging.config
import os

import yaml

from .configuration import Configuration
from .exceptions import HamasError, AgentError, TransmissionError, PortError, ConnectorError, MarketError, DeviceHandlerError, ConfigError
from .filter import PatternFilter, CSVFilter
from .management import *
from .transport import *

logging_conf = os.path.normpath(os.path.join(os.path.dirname(__file__), '../configuration/logging.yaml'))
with open(logging_conf, 'rt') as f:
    config = yaml.safe_load(f.read())
    if 'create_dir' in config:
        logs_path = os.path.abspath(config.pop('create_dir'))
        os.makedirs(logs_path, exist_ok=True)
    logging.config.dictConfig(config)
