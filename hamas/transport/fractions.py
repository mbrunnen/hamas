# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    21.10.2016
#   LICENSE:    MIT
#   FILE:       fractions.py
# =============================================================================
"""Fractions are the units on the transport layer.
"""

import math
import struct


class Fraction(object):
    port_fmt = 'B'
    seq_id_fmt = 'H'
    flag_fmt = 'c'
    header_fmt = '>' + port_fmt + seq_id_fmt + flag_fmt

    flag_encodings = {
        'SYN': b'\x00',
        'SYN-ACK': b'\x01',
        'DATA': b'\x02',
        'FIN': b'\x03',
        'RST': b'\x04',
        'URL': b'\x05',
        'JOIN': b'\x06',
    }
    flag_decodings = {v: k for k, v in flag_encodings.items()}

    def __init__(self, port, flag, seq_id=None, sdu=None):
        assert type(port) is int
        assert type(flag) is str
        assert type(seq_id) is int or seq_id is None
        assert type(sdu) is bytes or sdu is None
        assert port < 2 ** (8 * struct.calcsize(self.port_fmt)), "The port number {} is too high.".format(seq_id)
        self._port = port
        if seq_id is None:
            assert flag != 'DATA'
        self._seq_id = seq_id if seq_id is not None else 0
        assert self._seq_id < 2 ** (8 * struct.calcsize(self.seq_id_fmt)), \
            "The sequence ID {} is too high.".format(self._seq_id)
        self._flag = flag
        self._sdu = sdu
        self._frac_fmt = self.header_fmt + '{}s'.format(len(self._sdu)) if sdu else self.header_fmt

    def __hash__(self):
        return hash((self._port,
                     self._seq_id,
                     self._flag,
                     self._sdu))

    def __eq__(self, other):
        return self._port == other.port and \
               self._seq_id == other.seq_id and \
               self._flag == other.flag and \
               self._sdu == other.sdu

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "{}-Fraction (port: {}, seq.-ID: {})".format(self._flag, self._port, self._seq_id)

    def serialize(self):
        flag = self.flag_encodings[self._flag]
        if self._sdu:
            return struct.pack(self._frac_fmt, self._port, self._seq_id, flag, self._sdu)
        else:
            return struct.pack(self._frac_fmt, self._port, self._seq_id, flag)

    @property
    def port(self):
        return self._port

    @property
    def seq_id(self):
        return self._seq_id

    @property
    def flag(self):
        return self._flag

    @property
    def sdu(self):
        return self._sdu

    @classmethod
    def max_ports(cls):
        return 2 ** (8 * struct.calcsize(cls.port_fmt))

    @classmethod
    def header_len(cls):
        return struct.calcsize(cls.header_fmt)

    @classmethod
    def max_sdu_len(cls, mtu):
        return mtu - cls.header_len()

    @classmethod
    def max_size(cls, mtu):
        return cls.max_sdu_len(mtu) * (2 ** (8 * struct.calcsize('>' + cls.seq_id_fmt)) - 1)

    @classmethod
    def num_fractions(cls, msg, mtu):
        return math.ceil(len(msg) / cls.max_sdu_len(mtu))

    @classmethod
    def disassemble(cls, port, msg, mtu):
        """Prepare a message for sending.

        A agent to agent message is probably too long, so it needs to be separated in fractions.

        Args:
            port (int): The used port on both sides
            msg (bytes): The message which will be separated in fractions.
            mtu (int): The maximum transmission unit
        Returns:
            pdus (list): the ready to send PDUs

        """
        assert type(msg) is bytes
        assert len(msg) <= cls.max_size(mtu), "Message is too long!"
        pdus = []
        for idx, first in enumerate(range(0, len(msg), cls.max_sdu_len(mtu))):
            sdu = msg[first:first + cls.max_sdu_len(mtu)]
            frac = cls(port=port, flag='DATA', seq_id=idx, sdu=sdu)
            pdus.append(frac)
        return pdus

    @classmethod
    def deserialize(cls, serialized):
        """Disassemble a single fraction.

        Args:
            serialized (bytes):
        """
        sdu_len = len(serialized) - cls.header_len()
        if sdu_len > 0:
            frac_fmt = cls.header_fmt + '{}s'.format(sdu_len)
            port, seq_id, flags_encoded, sdu = struct.unpack(frac_fmt, serialized)
        else:
            sdu = None
            frac_fmt = cls.header_fmt
            port, seq_id, flags_encoded = struct.unpack(frac_fmt, serialized)
        return cls(port=port, flag=cls.flag_decodings[flags_encoded], seq_id=seq_id, sdu=sdu)

    @staticmethod
    def get_port(serialized):
        port = serialized[0]
        return port

    @staticmethod
    def assemble_msg(fractions):
        """ Assemble a serialized message out of fractions.

        The sequence ID can start at any number and can be overlapped,
        thus it needs to be passed as argument.

        Args:
            fractions (list):

        Returns:
            msg (bytes): The assembled, serialized message.

        """
        fraction_tuples = [(f.seq_id, f.sdu) for f in fractions]
        fraction_tuples = sorted(fraction_tuples, key=lambda tup: tup[0])
        return b''.join([t[1] for t in fraction_tuples])
