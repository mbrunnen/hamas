# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    25.10.2016
#   LICENSE:    MIT
#   FILE:       test_ports.py
# =============================================================================

import asyncio
import itertools
import logging
import os
import random
import struct
import unittest.mock

import pytest
import serial.tools.list_ports

from hamas.exceptions import TransmissionError, PortError
from hamas.transport.connectors.ports import Port
from hamas.transport.fractions import Fraction

log = logging.getLogger(__name__)
TESTNOZIGBEE = 'HAMASNOZIGBEE' in os.environ.keys() and os.environ['HAMASNOZIGBEE'] == '1'
TESTNOTCONNECTED = not [fd for fd, p, i in serial.tools.list_ports.grep('/dev/ttyUSB')] and not TESTNOZIGBEE
TESTZIGBEE = not TESTNOZIGBEE and not TESTNOTCONNECTED
log.setLevel(logging.DEBUG)


def make_coroutine(mock, event):
    async def coroutine(*args, **kwargs):
        event.set()
        return mock(*args, **kwargs)

    return coroutine


# noinspection PyUnresolvedReferences
class TestPort:
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_receive(self, zb):

        def get_fut(fl):
            return '_' + fl.lower().replace('-', '_')

        states = ['Listen', 'SYN-sent', 'Sending', 'Sent', 'SYN-received', 'Receiving', 'Received']
        flags = ['SYN', 'SYN-ACK', 'DATA', 'FIN', 'RST', 'URL']
        accepted_flags = ['SYN', 'SYN-ACK', 'DATA', 'FIN', 'RST']
        valid_transitions = {
            ('Listen', 'SYN'),
            ('SYN-sent', 'SYN-ACK'),
            ('Receiving', 'DATA'),
            ('Sent', 'FIN'),
            ('SYN-sent', 'RST'),
            ('Sending', 'RST'),
            ('Sent', 'RST'),
            ('SYN-received', 'RST'),
            ('Receiving', 'RST'),
            ('Received', 'RST'),
        }
        port_no = 0
        address = 'test'
        port = Port(port_no, zb, 1)
        for state, flag in itertools.product(states, flags):
            print("Testing to send {} in state {}".format(flag, state))
            fraction = Fraction(port_no, flag, seq_id=0)
            port._state = state
            port._other_address = address
            await port.receive(address, fraction)
            await port.receive(address, fraction)
            await port.receive(address, fraction)
            for fut_flag in accepted_flags:
                print("Checking future for {}.".format(fut_flag))
                frac_fut = getattr(port, get_fut(fut_flag))
                if fut_flag == flag and (state, flag) in valid_transitions:
                    # Future is set
                    if type(frac_fut) is asyncio.Queue:
                        # Queue
                        assert frac_fut.qsize() == 3
                        received_frac = await frac_fut.get()
                        assert received_frac == fraction
                        frac_fut.task_done()
                    else:
                        # Future
                        if state == 'Listen' and fut_flag == 'SYN':
                            assert frac_fut.result() == (address, fraction)
                        else:
                            assert frac_fut.result() == fraction
                else:
                    # Future is not set
                    if type(frac_fut) is asyncio.Queue:
                        assert frac_fut.qsize() == 0, "state: {}, flag: {}".format(state, flag)
                    else:
                        assert not frac_fut.done(), "state: {}, flag: {}".format(state, flag)
            port._clear()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_open(self, zb):

        listen_mock = unittest.mock.MagicMock()

        port_no = 80
        port = Port(port_no, zb, 1)
        # noinspection PyUnresolvedReferences
        with unittest.mock.patch.multiple(port, _listen=make_coroutine(listen_mock, port.listening)):
            await port.open()
            listen_mock.assert_called_once_with()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_send_closed(self, zb):

        called = asyncio.Event()

        syn_sent_mock = unittest.mock.MagicMock()
        port_no = 80
        port = Port(port_no, zb, 1)
        dest_address = 'test'
        message = b'test message'
        assert port._state == 'Closed'
        with unittest.mock.patch.multiple(port, _syn_sent=make_coroutine(syn_sent_mock, called)):
            asyncio.ensure_future(port.send(dest_address, message))
            await called.wait()
            syn_sent_mock.assert_called_once_with()
            assert port._message == message
            assert port._other_address == dest_address

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_close(self, zb):

        syn_sent_mock = unittest.mock.MagicMock()
        syn_send_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 1)
        dest_address = 'test'
        message = b'test message'
        assert port._state == 'Closed'
        with unittest.mock.patch.multiple(port, _syn_sent=make_coroutine(syn_sent_mock, syn_send_called)):
            asyncio.ensure_future(port.send(dest_address, message))
            await syn_send_called.wait()
            await port.close()
            assert port._state == 'Closed'
            assert not port.listening.is_set()
            assert port._transmission is None
            assert port._other_address is None
            assert port._message is None
            assert port._data_size is None
            assert port._outgoing_data == []
            assert port._incoming_data == []
            assert not port._syn.done()
            assert not port._syn_ack.done()
            assert port._data.empty()
            assert not port._fin.done()
            assert not port._rst.done()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_listen_active(self, zb):

        syn_sent_mock = unittest.mock.MagicMock()
        syn_send_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 1)
        assert port._state == 'Closed'
        with unittest.mock.patch.multiple(port, _syn_sent=make_coroutine(syn_sent_mock, syn_send_called)):
            await port.open()
            port._syn.set_result('send')
            await syn_send_called.wait()
            syn_sent_mock.assert_called_once_with()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_listen_passive(self, zb):

        synd_received_mock = unittest.mock.MagicMock()
        syn_received_called = asyncio.Event()
        port_no = 80
        port = Port(port_no, zb, 1)
        dest_addr = 'test'
        syn = Fraction(port_no, 'SYN')
        with unittest.mock.patch.multiple(port, _syn_received=make_coroutine(synd_received_mock, syn_received_called)):
            await port.open()
            port._syn.set_result((dest_addr, syn))
            await syn_received_called.wait()
            synd_received_mock.assert_called_once_with(dest_addr, syn)

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_syn_sent(self, zb):
        """
        A active open call on the port will trigger a SYN and let the port change to the state 'SYN-sent'
        """

        send_called = asyncio.Event()
        send_mock = unittest.mock.MagicMock()
        sending_called = asyncio.Event()
        sending_mock = unittest.mock.MagicMock()

        port_no = 80
        port = Port(port_no, zb, 0.01)
        dest_address = 'test'
        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '

        fractions = Fraction.disassemble(port_no, message)
        data_size = len(fractions)
        data_size_ser = struct.pack('>I', data_size)

        with unittest.mock.patch.multiple(port,
                                          _sending=make_coroutine(sending_mock, sending_called),
                                          _try_to_send=make_coroutine(send_mock, send_called)):
            asyncio.ensure_future(port.send(dest_address, message))
            await send_called.wait()
            send_called.clear()
            send_mock.assert_called_once_with(Fraction(port_no, 'SYN', sdu=data_size_ser), 'SYN-ACK')
            assert port._state == 'SYN-sent'
            assert fractions == port._outgoing_data

            await sending_called.wait()
            sending_mock.assert_called_once_with()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_syn_sent_no_reply(self, zb):
        """
        A active open call on the port will trigger a SYN and let the port change to the state 'SYN-sent'.
        No reply, will change the state to listen.
        """

        send_called = asyncio.Event()
        send_mock = unittest.mock.MagicMock()

        port_no = 80
        port = Port(port_no, zb, 0.001)
        dest_address = 'test'
        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '

        data_size = Fraction.num_fractions(message)
        data_size_ser = struct.pack('>I', data_size)
        with unittest.mock.patch.multiple(port, _try_to_send=make_coroutine(send_mock, send_called)):
            send_mock.side_effect = PortError("Nope.")
            transmission = asyncio.ensure_future(port.send(dest_address, message))
            await send_called.wait()
            send_called.clear()
            send_mock.assert_called_once_with(Fraction(port_no, 'SYN', sdu=data_size_ser), 'SYN-ACK')

            with pytest.raises(PortError):
                await transmission
            assert port._outgoing_data == []
            await port.listening.wait()
            assert port._state == 'Listen'
            await port.close()
            assert port._state == 'Closed'

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_sending(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()
        send_data_mock = unittest.mock.MagicMock()
        send_data_called = asyncio.Event()
        sent_mock = unittest.mock.MagicMock()
        sent_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 0.01)
        dest_address = 'test'
        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '
        Fraction._mtu = 20

        fractions = Fraction.disassemble(port_no, message)
        data_size = len(fractions)
        data_size_ser = struct.pack('>I', data_size)
        assert port._state == 'Closed'
        with unittest.mock.patch.multiple(port,
                                          _try_to_send=make_coroutine(send_mock, send_called),
                                          _send_data=make_coroutine(send_data_mock, send_data_called),
                                          _sent=make_coroutine(sent_mock, sent_called)):
            asyncio.ensure_future(port.send(dest_address, message))
            await send_called.wait()
            send_called.clear()
            assert port._state == 'Sending'
            send_mock.assert_called_once_with(Fraction(port_no, 'SYN', sdu=data_size_ser), 'SYN-ACK')
            assert port._outgoing_data == fractions
            await send_data_called.wait()
            send_data_mock.assert_called_once_with()
            await sent_called.wait()
            sent_mock.assert_called_once_with()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_sent(self, zb):

        port_no = 80
        other_address = 'test'
        port = Port(port_no, zb, 1)
        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '
        Fraction._mtu = 20

        assert port._state == 'Closed'
        port._other_address = other_address
        port._outgoing_data = Fraction.disassemble(port_no, message)
        task = asyncio.ensure_future(port._sent())
        await asyncio.sleep(port._timeout / 2)
        assert port._state == 'Sent'
        await port.receive(other_address, Fraction(port_no, 'FIN'))
        await port.listening.wait()
        assert port._state == 'Listen'
        await port.close()
        assert port._state == 'Closed'
        await task

        assert not port._fin.done()
        task = asyncio.ensure_future(port._sent())
        await asyncio.sleep(port._timeout / 2)
        assert port._state == 'Sent'
        await port.listening.wait()
        assert port._state == 'Listen'
        await port.close()
        assert port._state == 'Closed'
        with pytest.raises(PortError) as exc:
            await task
        assert exc.match("didn't get any response.")

        assert port._state == 'Closed'
        port._other_address = other_address
        port._outgoing_data = Fraction.disassemble(port_no, message)
        task = asyncio.ensure_future(port._sent())
        await asyncio.sleep(port._timeout / 2)
        assert port._state == 'Sent'
        await port.receive(other_address, Fraction(port_no, 'RST'))
        await port.listening.wait()
        assert port._state == 'Listen'
        await port.close()
        assert port._state == 'Closed'
        with pytest.raises(PortError) as exc:
            await task
        assert exc.match("send data but the receiving port got corrupted data.")

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_syn_received(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()
        receiving_mock = unittest.mock.MagicMock()
        receiving_called = asyncio.Event()
        reopen_mock = unittest.mock.MagicMock()
        reopen_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 1)
        dest_address = 'test'

        data_size = 100
        data_size_ser = struct.pack('>I', data_size)
        syn = Fraction(port_no, 'SYN', sdu=data_size_ser)

        assert port._state == 'Closed'
        await port.open()
        with unittest.mock.patch.multiple(zb, send_fraction=make_coroutine(send_mock, send_called)):
            with unittest.mock.patch.multiple(port,
                                              _receiving=make_coroutine(receiving_mock, receiving_called),
                                              _reopen=make_coroutine(reopen_mock, reopen_called)):
                asyncio.ensure_future(port.receive(dest_address, syn))
                await send_called.wait()
                send_called.clear()
                assert port._state == 'SYN-received'
                send_mock.assert_called_once_with(dest_address, Fraction(port_no, 'SYN-ACK'))
                assert port._other_address is dest_address
                assert port._data_size == data_size
                await receiving_called.wait()
                receiving_mock.assert_called_once_with()
                await port.close()
                assert port._state == 'Closed'
                assert not send_called.is_set()
                send_mock.reset_mock()

                asyncio.ensure_future(port.receive(dest_address, syn))
                await send_called.wait()
                send_called.clear()
                assert port._state == 'Closed'
                send_mock.assert_called_once_with(dest_address, Fraction(port_no, 'RST'))
                await port.close()
                assert not send_called.is_set()
                send_mock.reset_mock()

                await port.open()
                assert port._state == 'Listen'
                send_mock.side_effect = TransmissionError('Nope.')
                asyncio.ensure_future(port.receive(dest_address, syn))
                await send_called.wait()
                assert port._other_address is dest_address
                assert port._data_size == data_size
                await reopen_called.wait()
                reopen_mock.assert_called_once_with()
                await port.close()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_receiving(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()
        received_mock = unittest.mock.MagicMock
        received_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 0.01)
        dest_address = 'test'

        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '
        Fraction._mtu = 20

        fractions = Fraction.disassemble(port_no, message)
        data_size = len(fractions)
        data_size_ser = struct.pack('>I', data_size)
        syn = Fraction(port_no, 'SYN', sdu=data_size_ser)
        port._timeout = 1
        await port.open()
        with unittest.mock.patch.multiple(zb, send_fraction=make_coroutine(send_mock, send_called)):
            with unittest.mock.patch.multiple(port, _received=make_coroutine(received_mock, received_called)):
                asyncio.ensure_future(port.receive(dest_address, syn))
                await send_called.wait()
                await asyncio.sleep(port._timeout / 2)
                assert port._state == 'Receiving'
                expected_data = fractions.copy()
                fractions += fractions.copy()
                random.shuffle(fractions)
                await asyncio.wait([asyncio.ensure_future(port.receive(dest_address, d)) for d in fractions])
                await received_called.wait()
                incoming_data = set(port._incoming_data)
                assert len(port._incoming_data) == len(expected_data)
                assert len(incoming_data ^ set(expected_data)) == 0

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_received(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()
        reopen_mock = unittest.mock.MagicMock()
        reopen_called = asyncio.Event()
        receiving_mock = unittest.mock.MagicMock()
        receiving_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 0.01)
        Fraction._mtu = 20
        dest_address = 'test'

        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '
        incoming_data = Fraction.disassemble(port_no, message)

        with unittest.mock.patch.multiple(zb, send_fraction=make_coroutine(send_mock, send_called)):
            with unittest.mock.patch.multiple(port,
                                              _reopen=make_coroutine(reopen_mock, reopen_called),
                                              _receiving=make_coroutine(receiving_mock, receiving_called)):
                port._data_size = len(incoming_data)
                port._incoming_data = incoming_data.copy()
                port._incoming_data.pop(0)
                port._other_address = dest_address
                await port._received()
                await send_called.wait()
                send_mock.assert_called_once_with(dest_address, Fraction(port_no, 'RST'))
                reopen_mock.assert_called_once_with()
                send_called.clear()
                send_mock.reset_mock()
                reopen_mock.reset_mock()

                port._incoming_data = incoming_data.copy()
                port._other_address = dest_address
                await port._received()
                await send_called.wait()
                send_mock.assert_called_once_with(dest_address, Fraction(port_no, 'FIN'))
                reopen_mock.assert_called_once_with()
                send_called.clear()
                send_mock.reset_mock()
                reopen_mock.reset_mock()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_transmission_passive(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()

        # log.setLevel(logging.INFO)
        log.setLevel(logging.DEBUG)
        port_no = 80
        port = Port(port_no, zb, 1)
        Fraction._mtu = 20
        source_address = 'test'
        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '

        data_size = Fraction.num_fractions(message)
        data_size_ser = struct.pack('>I', data_size)

        await port.open()
        with unittest.mock.patch.multiple(zb, send_fraction=make_coroutine(send_mock, send_called), deliver=unittest.mock.DEFAULT):
            syn = Fraction(port_no, 'SYN', sdu=data_size_ser)
            await port.receive(source_address, syn)
            await send_called.wait()
            assert port._state == 'Receiving'
            send_called.clear()
            send_mock.assert_called_once_with(source_address, Fraction(port_no, 'SYN-ACK'))
            send_mock.reset_mock()
            incoming_data = Fraction.disassemble(port_no, message)
            random.shuffle(incoming_data)
            await asyncio.sleep(port._timeout / 2)
            await asyncio.wait([asyncio.ensure_future(port.receive(source_address, d)) for d in incoming_data])
            await port.listening.wait()
            assert port._state == 'Listen'
            await port.close()
            assert port._state == 'Closed'
            send_mock.assert_called_once_with(source_address, Fraction(port_no, 'FIN'))
            zb.deliver.assert_called_once_with(message)

    @pytest.mark.parametrize('tries', list(range(3, 4)))
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_transmission_both(self, zb, tries):
        def make_send(mock, event, p_1, p_2, to, probability, max_attempts):
            async def send_wrapper(dest_addr, frac):
                delay = to * random.random() * 0.01
                await asyncio.sleep(delay)
                attempt = 0
                while attempt < max_attempts:
                    if random.random() < probability:
                        if dest_addr == 'port 1':
                            await p_1.receive('port 2', frac)
                        elif dest_addr == 'port 2':
                            await p_2.receive('port 1', frac)
                        else:
                            assert False
                        break
                    else:
                        log.debug("Failed to send Fraction ({}) to {} in attempt {:d}.".format(frac, dest_addr, attempt))
                        attempt += 1

                if attempt == max_attempts:
                    print("FAAAAAAAAAAAAAAAIIIIIIIL")
                    raise TransmissionError

                event.set()
                return mock(dest_addr, frac)

            return send_wrapper

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()

        log.setLevel(logging.DEBUG)
        # log.setLevel(logging.INFO)
        # log.setLevel(logging.WARNING)
        # log.setLevel(logging.ERROR)

        timeout = 0.01
        num_fracs = 10
        send_probability = 0.8
        rounds = 100

        port_1 = Port(80, zb, timeout)
        port_2 = Port(200, zb, timeout)

        mtu = 20
        Fraction._mtu = mtu
        addr_1 = 'port 1'
        addr_2 = 'port 2'

        await port_2.open()
        assert port_2._state == 'Listen'

        flags = ['SYN', 'SYN-ACK', 'DATA', 'DATA-SACK', 'FIN', 'FIN-ACK', 'RST', 'ACK']
        with unittest.mock.patch.multiple(zb,
                                          send_fraction=make_send(send_mock, send_called, port_1, port_2, timeout, send_probability, tries),
                                          deliver=unittest.mock.DEFAULT):

            success_counter = 0

            async def transmit(sender, receiver, receiver_addr):
                print("===================================")
                print("New Transmission from {} to {}".format(sender, receiver))
                print("===================================")

                message = os.urandom(num_fracs * Fraction.max_sdu_len())
                assert Fraction.num_fractions(message) == num_fracs
                success = False
                try:
                    await sender.send(receiver_addr, message)
                except TransmissionError as exc:
                    print("Sender: {}".format(sender))
                    print("Receiver: {}".format(receiver))
                    log.exception(exc)
                    await receiver.listening.wait()
                else:
                    await receiver.listening.wait()
                    zb.deliver.assert_called_once_with(message)
                    success = True

                await receiver.listening.wait()
                assert sender._state == 'Listen'
                assert receiver._state == 'Listen'
                zb.deliver.reset_mock()
                print("===================================")
                print("Transmission finished")
                print("===================================")
                return success

            for i in range(rounds):
                tr = await transmit(port_1, port_2, addr_2)
                if tr:
                    success_counter += 1
                tr = await transmit(port_2, port_1, addr_1)
                if tr:
                    success_counter += 1

            await port_1.close()
            assert port_1._state == 'Closed'
            await port_2.close()
            assert port_2._state == 'Closed'

            fracs = [arg[0][1] for arg in send_mock.call_args_list]
            sent_flags = [f.flag for f in fracs]
            for f in flags:
                print("{}: {:.2%}".format(f, sent_flags.count(f) / len(sent_flags)))
            print("Transmission success rate is {:.2%} with a send probability of {:.2%}".format(success_counter / (2 * rounds), send_probability))
            print("Send was called in average {:.2f} times for transmitting {:d} fractions.".format(send_mock.call_count / (2 * rounds), num_fracs))

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_send_data(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()

        port_no = 80
        port = Port(port_no, zb, 1)
        message = b'Hello World. ' \
                  + b'These are fractions. ' \
                  + b'ZigBee cannot send so much data. ' \
                  + b'So I split the Messages in multiple frames. ' \
                  + b'Let\'s see if we can put them together in the right order. '
        Fraction._mtu = 20
        port._outgoing_data = Fraction.disassemble(port_no, message)
        with unittest.mock.patch.multiple(zb, send_fraction=make_coroutine(send_mock, send_called)):
            send_mock.reset_mock()
            await port._send_data()
            sent_data = [arg[0][1] for arg in send_mock.call_args_list]
            assert len(sent_data) == len(port._outgoing_data)
            assert sent_data == port._outgoing_data

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_try_to_send(self, zb):

        send_mock = unittest.mock.MagicMock()
        send_called = asyncio.Event()
        port_no = 80
        port = Port(port_no, zb, 0.1)
        dest_address = 'test'
        port._other_address = dest_address

        syn = Fraction(port_no, 'SYN')

        with unittest.mock.patch.multiple(zb, send_fraction=make_coroutine(send_mock, send_called)):
            with pytest.raises(PortError) as exc:
                await port._try_to_send(syn, 'SYN-ACK')
            assert exc.match("did not get a response to a")
            send_called.clear()

            response_fut = asyncio.ensure_future(port._try_to_send(syn, 'SYN-ACK'))
            await send_called.wait()
            syn_ack = Fraction(port_no, 'SYN-ACK')
            port._syn_ack.set_result(syn_ack)
            response = await response_fut
            assert response == syn_ack
            send_called.clear()

            send_mock.side_effect = TransmissionError('Nope.')
            with pytest.raises(PortError) as exc:
                await port._try_to_send(syn, 'SYN-ACK')
            assert exc.match("Sending data on")
            await port.close()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    def test_add_data(self, zb):
        port_no = 80
        port = Port(port_no, zb, 1)
        last_frac = Fraction(port_no, 'SYN-ACK')
        port._last_sent_frac = last_frac
        data_1 = Fraction(port_no, 'DATA', 0, sdu=b'first')
        port._add_data(data_1)
        assert len(port._incoming_data) == 1

        port._add_data(data_1)
        assert len(port._incoming_data) == 1

        data_2 = Fraction(port_no, 'DATA', seq_id=data_1.seq_id, sdu=b'same')
        port._add_data(data_2)
        assert len(port._incoming_data) == 1

        data_3 = Fraction(port_no, 'DATA', 1, sdu=b'same')
        port._add_data(data_3)
        assert len(port._incoming_data) == 2
