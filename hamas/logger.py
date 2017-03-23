# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    10.01.2017
#   LICENSE:    MIT
#   FILE:       logger.py
# =============================================================================
""" Implement the HAMAS Logger.
"""

import logging.config
import os
import sys
import csv
import io
import logging
import re

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
        logging.basicConfig(
            style=style,
            format=fmt,
            datefmt=date_fmt,
            level=level,
            stream=sys.stdout)


class PatternFilter(object):

    def __init__(self, patterns):
        self._patterns = patterns

    def filter(self, record):
        name = record.name

        if record.levelno >= logging.ERROR:
            return True
        for pattern in self._patterns:
            if re.search(pattern, name):
                return True
        return False


class CSVFilter(object):
    def __init__(self, context):
        self._header_printed = False
        self._context = context

    def filter(self, record):

        if hasattr(record,
                   'data_context') and record.data_context == self._context:
            data = record.data
            data['timestamp'] = record.created
            output = io.StringIO()
            writer = csv.DictWriter(
                output, fieldnames=sorted(data.keys()), lineterminator='')
            if not self._header_printed:
                writer.writeheader()
                output.write('\n')
                self._header_printed = True
            writer.writerow(data)
            record.row = output.getvalue()
            return True
        else:
            return False
