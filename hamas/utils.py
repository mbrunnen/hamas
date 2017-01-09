# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    14.12.2016
#   LICENSE:    MIT
#   FILE:       utils.py
# =============================================================================
"""Useful functions
"""

import codecs
import struct


def hexstr2bytes(hexstring):
    """Convert a hexstring like '04' to b'\x04'
    """
    return codecs.decode(hexstring, 'hex')


def bytes2hexstr(bytestr):
    """Convert bytes, e.g. a parameter, to a human readable string.

    For example, normally b'\x77' will be printed as b'w', which is not wanted for hexadecimal addresses.
    To avoid this, this method transforms the bytes object b'\x77' to the string '77'

    Args:
        bytestr(bytes): A bytestring with hexadecimal values.

    Returns:
        hexstring(str): A string containing the hexdecimal numbers as string, e.g. b'\x4A' will become '4A'

    """
    assert type(bytestr) is bytes
    return codecs.encode(bytestr, 'hex').decode().upper()


def int2bytes(i):
    """Convert an int to a byte, like 255 to b'\xFF'
    """
    return struct.pack('>I', i)


def bytes2uint(bytestring):
    return int.from_bytes(bytestring, 'big')
