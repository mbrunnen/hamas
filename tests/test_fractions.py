# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    23.10.2016
#   LICENSE:    MIT
#   FILE:       test_fractions.py
# =============================================================================

import itertools
import logging
import os
import random
import struct
import time

import pytest

from hamas.transport.fractions import Fraction

log = logging.getLogger(__name__)

ports = [80, 22]
flags = ['SYN', 'SYN-ACK', 'DATA', 'FIN', 'RST', 'URL', 'JOIN']
seqs = [0, 100, 0xffff, 0xffff - 1, 0xffff - 2]
msgs = [b'a message', b'another message', None]
isns = [0xffff - 2, 0xffff - 1, 0xffff, 0, 1, 2, 100]

log.setLevel(logging.INFO)


class TestFraction:
    @pytest.mark.parametrize('port, flag, seq_id, sdu', itertools.product(ports, flags, seqs, msgs))
    def test_init(self, port, flag, seq_id, sdu):
        frac = Fraction(port, flag, seq_id, sdu)
        assert frac.port == port
        assert frac.flag == flag
        if seq_id is not None:
            assert frac.seq_id == seq_id
        else:
            assert frac.seq_id
        assert frac.sdu == sdu

        with pytest.raises(AssertionError):
            Fraction(0xff + 1, 'test', 100, b'test')
        with pytest.raises(AssertionError):
            Fraction(80, 'test', 0xffff + 1, b'test')
        with pytest.raises(AssertionError):
            Fraction(80, b'test', 100, b'test')

    def test_equality(self):
        less_flags = ['SYN', 'DATA']
        valid_args = [a for a in itertools.product(ports, less_flags, seqs, msgs)]
        for args1, args2 in itertools.product(valid_args, valid_args):
            msg1 = Fraction(*args1)
            msg2 = Fraction(*args2)
            if args1 == args2:
                assert msg1 == msg2
                assert msg2 == msg1
            else:
                assert msg1 != msg2
                assert msg2 != msg1

    @pytest.mark.parametrize('flag, seq_id, sdu', itertools.product(flags, seqs, [b'test', None]))
    def test_serialize(self, flag, seq_id, sdu):
        frac = Fraction(80, flag, seq_id, sdu)
        serialized = frac.serialize()
        assert type(serialized) is bytes
        deserialized = Fraction.deserialize(serialized)
        assert frac == deserialized
        log.debug("Length of the serialized {} is {:d}".format(
            frac.__class__.__name__, len(serialized)))

    def test_disassemble(self):
        mtu = 20
        dest_port = 80
        assert Fraction.max_size(mtu) == Fraction.max_sdu_len(mtu) * 0xffff
        with pytest.raises(AssertionError):
            msg = os.urandom((2 ** 16) * Fraction.max_sdu_len(mtu))
            Fraction.disassemble(port=dest_port, msg=msg, mtu=mtu)
        msg = b'Hello World. ' \
              + b'These are fractions. ' \
              + b'ZigBee cannot send so much data. ' \
              + b'So I split the Messages in multiple frames. ' \
              + b'Let\'s see if we can put them together in the right order. '
        fractions = Fraction.disassemble(port=dest_port, msg=msg, mtu=mtu)
        port_ser = b'\x50'
        flag_code = b'\x02'
        sdus = [
            b'Hello World. The',
            b'se are fractions',
            b'. ZigBee cannot ',
            b'send so much dat',
            b'a. So I split th',
            b'e Messages in mu',
            b'ltiple frames. L',
            b"et's see if we c",
            b'an put them toge',
            b'ther in the righ',
            b't order. '
        ]

        expected_fractions = []
        seq_id = 0
        for sdu in sdus:
            pdu = port_ser + struct.pack('>H', seq_id) + flag_code + sdu
            expected_fractions.append(pdu)
            seq_id += 1

        assert len(fractions) == Fraction.num_fractions(msg, mtu)
        assert list(range(Fraction.num_fractions(msg, mtu))) == [f.seq_id for f in fractions]
        serialized_pdus = [p.serialize() for p in fractions]
        assert serialized_pdus == expected_fractions

    def test_assemble_msg(self):
        mtu = 20
        dest_port = 80
        # make it big
        msg = os.urandom(Fraction.max_size(mtu))
        fractions = Fraction.disassemble(port=dest_port, msg=msg, mtu=mtu)
        # simulate sending
        serialized_fractions = [f.serialize() for f in fractions]
        random.shuffle(serialized_fractions)
        # simulate receiving
        deserialized_fractions = [Fraction.deserialize(f) for f in serialized_fractions]
        start = time.monotonic()
        reassembled_msg = Fraction.assemble_msg(deserialized_fractions)
        end = time.monotonic()
        log.info("Reassembling {} kB took {:.2f} ms".format(len(msg) / 1000, (end - start) * 1000))
        assert reassembled_msg == msg
