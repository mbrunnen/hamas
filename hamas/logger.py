# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    10.01.2017
#   LICENSE:    MIT
#   FILE:       logger.py
# =============================================================================
""" Configure the HAMAS Logger
"""

import logging.config
import os
import sys

import yaml


def config_logger(logger_config_file=None):
    """Call this function to enable a fully configurable logger for this package.

    Kwargs:
        logger_config_file (str): Path of logging configuration file.

    """
    if logger_config_file is not None:

        with open(logger_config_file, 'rt') as f:
            config = yaml.safe_load(f.read())
        for h in config['handlers'].values():
            if 'filename' in h:
                dir = os.path.dirname(h['filename'])
                os.makedirs(dir, exist_ok=True)
        logging.config.dictConfig(config)
    else:
        fmt = '{levelname}\t{asctime}\t{name:50}\tl:{lineno}\t{message}'
        style = '{'
        date_fmt = '%d-%m-%y %H:%M:%S'
        level = 'INFO'
        logging.basicConfig(style=style, format=fmt, datefmt=date_fmt, level=level, stream=sys.stdout)
