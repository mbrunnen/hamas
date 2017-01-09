# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    15.10.2016
#   LICENSE:    MIT
#   FILE:       serializable.py
# =============================================================================
"""Serializable objects like messages and Payloads

Classes which inherits from this class have to overwrite _get_init_args to
be serializable.
"""

import marshal
import pickle
import struct
from abc import ABC


class Serializable(ABC):
    """Objects which can be transformed to a bytes object
    """
    _code = None

    serializers = {
        b'\x01': 'hamas.management.contents.RemoteProcessCall',
        b'\x02': 'hamas.management.contents.RemoteProcessReply',
        b'\x03': 'hamas.management.contents.StringContent',
        b'\x04': 'hamas.management.contents.DictionaryContent',
        b'\x05': 'hamas.management.messages.Message',
        b'\x08': 'hamas.ems.ems_contents.EMSContent',
        b'\x09': 'hamas.ems.ems_contents.BidCollection',
        b'\x0A': 'hamas.ems.ems_contents.Bid',
    }

    def _get_init_args(self):
        """Helper function for the serialization

        Returns:
            args (tuple): the positional constructor arguments as tuple

        """
        return ()

    def serialize(self):
        """Serialize this instance to a bytes object

        Returns:
             serialized (bytes): The serialized object.

        """
        init_args = self._get_init_args()
        assert type(init_args) is tuple
        assert self._code
        return self._code + marshal.dumps(init_args)

    @classmethod
    def deserialize(cls, serialized):
        """Deserialize a bytes object to a Content object

        Args:
            serialized(bytes): The serialized object.

        Returns:
            payload(Content): Returns an instance of the class Content

        """
        assert type(serialized) is bytes
        code, data = struct.unpack('c{:d}s'.format(len(serialized) - 1), serialized)
        assert code == cls._code
        init_args = marshal.loads(data)
        return cls(*init_args)

    def pickle(self):
        return pickle.dumps(self)

    @staticmethod
    def unpickle(serialized):
        assert type(serialized) is bytes
        return pickle.loads(serialized)
