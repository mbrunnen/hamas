# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    01.12.2016
#   LICENSE:    MIT
#   FILE:       filter.py
# =============================================================================


import csv
import io
import logging
import re


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

        if hasattr(record, 'data_context') and record.data_context == self._context:
            data = record.data
            data['timestamp'] = record.created
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=sorted(data.keys()), lineterminator='')
            if not self._header_printed:
                writer.writeheader()
                output.write('\n')
                self._header_printed = True
            writer.writerow(data)
            record.row = output.getvalue()
            return True
        else:
            return False
