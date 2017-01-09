# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    05.10.2016
#   LICENSE:    MIT
#   FILE:	    test_zigbee.py
# =============================================================================
"""Test the ZigBee interface
"""

import asyncio
import logging
import os
import random
import re
import string
import time
import unittest.mock

import pytest
import serial
import serial.tools.list_ports

from hamas import ConnectorError
from hamas import Fraction
from hamas import Message
from hamas import StringContent
from hamas import TransmissionError
from hamas import ZigBeeConnector

log = logging.getLogger(__name__)

TESTNOZIGBEE = 'HAMASNOZIGBEE' in os.environ.keys() and os.environ['HAMASNOZIGBEE'] == '1'
TESTNOTCONNECTED = not [fd for fd, p, i in serial.tools.list_ports.grep('/dev/ttyUSB')] and not TESTNOZIGBEE
TESTZIGBEE = not TESTNOZIGBEE and not TESTNOTCONNECTED
log.setLevel(logging.INFO)


class TestZigbee:
    """Test Case for the ZigBee interface"""

    @pytest.mark.skipif(not TESTNOZIGBEE, reason="Set $HAMASNOZIGBEE to test it.")
    def test_nozigbee(self, event_loop, machine_name):
        with pytest.raises(ConnectorError) as exception:
            ZigBeeConnector(event_loop, machine_name)
        exception.match('ZigBee is disabled.')

    @pytest.mark.skipif(not TESTNOTCONNECTED, reason="ZigBee module available.")
    def test_not_connected(self, event_loop, machine_name):
        with pytest.raises(ConnectorError) as exception:
            ZigBeeConnector(event_loop, machine_name)
        exception.match('No serial device found.')

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled.")
    def test_create(self, event_loop, machine_name):
        usbport = '/dev/ttyUSB'
        ports = [fd for fd, p, i in serial.tools.list_ports.grep(usbport)]
        assert len(ports) == 1
        zb = ZigBeeConnector(event_loop, machine_name)
        assert type(zb._serial) is serial.Serial
        assert isinstance(zb._loop, asyncio.BaseEventLoop)
        assert zb._callback is None
        zb.stop()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    def test_generate_fid(self, zb):
        """Test if the frame ID is assigned as intended
        """

        assert zb._current_frame_id == 0
        frame_ids = [zb._generate_frame_id() for _ in range(512)]

        assert ord(frame_ids[0]) == 1
        assert len(frame_ids) > 256
        for i, f_id in enumerate(frame_ids):
            assert ord(f_id) > 0
            assert ord(f_id) < 256
            assert ord(f_id) == (i % 255) + 1

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_send_command(self, event_loop, machine_name):
        """ Get the other participants in the network.
        """
        zb = ZigBeeConnector(event_loop, machine_name, serial_timeout=10)
        await zb.start()
        responses = await zb.send_command(cmd='at', command=b'ND', num_items=2)
        assert len(responses) == 2
        for r in responses:
            assert r['id'] == 'at_response'
            assert r['command'] == b'ND'
            assert r['parameter']['status'] == b'\x00'
            print(r['parameter']['node_identifier'].decode())
            print(r['parameter']['source_addr'])
            print(r['parameter']['source_addr_long'])
        zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_transmission_failed(self, event_loop, machine_name):
        zb = ZigBeeConnector(event_loop, machine_name, serial_timeout=0.1, others_timeout=1)
        await zb.start()
        addr = '00:12:34:56:78:9A:BC:DF!ABCD'
        with pytest.raises(TransmissionError) as exc:
            zb.response_timeout = 2
            frac = Fraction(1, 'DATA')
            await zb.send_fraction(addr, frac)
            exc.match('Transmission failed with status')
        zb.stop()

    def test_parser_noshort(self):
        long_addr = b'\xde\xad\xbe\xef\x42\x00\x00\x00'
        address = ZigBeeConnector.compose_address(long_addr)
        assert long_addr != address
        assert address == 'DE:AD:BE:EF:42:00:00:00'
        parsed_long_addr, parsed_short_addr = ZigBeeConnector.parse_address(address)
        assert parsed_long_addr == long_addr
        assert parsed_short_addr == b'\xFF\xFE'

    def test_parser_both(self):
        long_addr = b'\xde\xad\xbe\xef\x42\x00\x00\x00'
        short_addr = b'\x12\xAB'
        address = ZigBeeConnector.compose_address(long_addr, short_addr)
        assert address == 'DE:AD:BE:EF:42:00:00:00!12AB'
        parsed_long_addr, parsed_short_addr = ZigBeeConnector.parse_address(address)
        assert parsed_long_addr == long_addr
        assert parsed_short_addr == short_addr

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    def test_get_port(self, zb):
        i = 0
        for port in zb._get_port():
            assert port.is_free()
            assert 0 <= port.number < 255
            i += 1
        assert i == 255

    @pytest.mark.parametrize('msg', [Message('someone', StringContent('test string'), 'someone else', 'somehow', None),
                                     Message('someone', StringContent('test string'), None, 'somehow', None),
                                     Message('someone', StringContent('test string'), None, 'somehow', 100),
                                     ])
    def test_deserialize_message(self, msg):
        serialized_msg = msg.serialize()
        assert type(serialized_msg) is bytes
        deserialzed_msg = ZigBeeConnector._deserialize_message(serialized_msg)
        assert deserialzed_msg == msg

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_get_address(self, event_loop, machine_name):
        zb = ZigBeeConnector(event_loop, machine_name)
        await zb.start()
        assert zb.address == '00:13:A2:00:41:48:13:5F!0000'
        response_high = await zb.send_command(cmd='at', command=b'SH', num_items=1)
        assert len(response_high) == 1
        response_low = await zb.send_command(cmd='at', command=b'SL', num_items=1)
        assert len(response_low) == 1
        response_my = await zb.send_command(cmd='at', command=b'MY', num_items=1)
        address = zb.compose_address(response_high[0]['parameter'] + response_low[0]['parameter'], response_my[0]['parameter'])
        assert address == zb.address
        zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_update_others_requesting(self, event_loop):
        log.setLevel(logging.DEBUG)
        zb = ZigBeeConnector(event_loop, 'updating_machine')
        try:
            others = zb.other_machines
            assert len(others) == 0
            await zb.start()
            await zb.wait_for_others()
            await asyncio.sleep(10)
            others = zb._other_machines
            assert len(others) > 0
            print("Other Machines found: {}".format(zb.other_machines))
            if len(others) == 1:
                assert re.match('00:13:A2:00:41:48:13:77!', others['receiving_machine'])
            else:
                assert re.match('00:13:A2:00:41:48:13:77!', others['emasem01'])
                assert re.match('00:13:A2:00:41:48:12:EA!', others['emasem02'])

        finally:
            zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_get_mtu(self, event_loop, machine_name):
        zb = ZigBeeConnector(event_loop, machine_name)
        await zb.start()
        mtu = await zb.get_mtu()
        assert mtu == 255
        zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_unicast(self, event_loop):
        def reply_received(message):
            log.info("Got message:\n\t{}".format(message))
            got_reply.set_result(message)

        log.setLevel(logging.INFO)

        zb = ZigBeeConnector(event_loop, 'sending_machine', callback=reply_received)
        text = ''.join(random.choice(string.printable) for _ in range(2500))
        try:
            got_reply = asyncio.Future()
            await zb.start()
            assert len(zb.other_machines) == 1
            msg = Message(sender=zb.machine_name, content=StringContent(text))
            start = time.monotonic()
            await zb.unicast(message=msg, machine_name=zb.other_machines[0])
            tm_end = time.monotonic()
            reply = await got_reply
            rp_end = time.monotonic()
            assert reply.content == msg.content
            print("The message is:\n{}\n".format(reply.content.string))
            print("Transmission took {:f}s.".format(tm_end - start))
            print("The reply arrived {:f}s after transmission.".format(rp_end - tm_end))
            print("The conversation took {:f}s.".format(rp_end - start))
        finally:
            zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_broadcast(self, event_loop):
        def reply_received(message):
            log.info("Got message:\n\t{}".format(message))
            replies.put_nowait(message)

        log.setLevel(logging.DEBUG)

        zb = ZigBeeConnector(event_loop, 'sending_machine', callback=reply_received)
        text = ''.join(random.choice(string.printable) for _ in range(5 * Fraction.max_sdu_len()))
        try:
            replies = asyncio.Queue()
            msg = Message(sender=zb.machine_name, content=StringContent(text))
            await zb.start()
            await zb.wait_for_others()
            start = time.monotonic()
            await zb.broadcast(message=msg)
            tm_end = time.monotonic()
            for i, _ in enumerate(zb.other_machines):
                reply = await replies.get()
                rp_end = time.monotonic()
                assert reply.content == msg.content
                print("The reply from {} arrived {:f}s after transmission.".format(reply.sender, rp_end - tm_end))
            end = time.monotonic()

            print("Transmission took {:f}s.".format(tm_end - start))
            print("The whole conversation took {:f}s.".format(end - start))
        finally:
            log.setLevel(logging.INFO)
            zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_send_handler(self, event_loop):
        zb = ZigBeeConnector(event_loop, 'test', serial_timeout=0.1)
        with unittest.mock.patch.object(zb._zigbee, 'send', unittest.mock.DEFAULT) as mock:
            task = asyncio.ensure_future(zb._send_handler())
            response_fut = asyncio.Future()
            response_fut.set_result('done')
            send_kwargs = {'test': 'string'}
            await zb._send_queue.put((response_fut, send_kwargs))
            await zb._send_queue.join()
            mock.assert_called_once_with(test='string')

            assert not task.done()
            response_fut = asyncio.Future()
            await zb._send_queue.put((response_fut, send_kwargs))
            await zb._send_queue.join()
            assert mock.call_count == 2

            assert not task.done()
            response_fut = asyncio.Future()
            await zb._send_queue.put((response_fut, send_kwargs))
            await zb._send_queue.join()
            assert mock.call_count == 3

            task.cancel()
            zb.stop()


class TestRemote:
    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_recast_1(self, event_loop):
        log.setLevel(logging.DEBUG)

        def set_message(message):
            got_message.set_result(message)

        log.setLevel(logging.DEBUG)
        zb = ZigBeeConnector(event_loop, 'emasem01', callback=set_message)

        await zb.start()
        try:
            while True:
                got_message = asyncio.Future()
                log.info("Node {} is listening ...".format(zb.address))
                received_msg = await got_message
                reply = Message(sender=zb.address, content=received_msg.content)
                try:
                    await zb.unicast(message=reply, machine_name='sending_machine')
                except TransmissionError as exc:
                    log.exception(exc)
                log.info("Finished. Here is the message again:\n\t{}".format(received_msg.content.string))

        finally:
            zb.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    async def test_recast_2(self, event_loop):
        log.setLevel(logging.DEBUG)

        def set_message(message):
            got_message.set_result(message)

        log.setLevel(logging.DEBUG)
        zb = ZigBeeConnector(event_loop, 'emasem02', callback=set_message)

        await zb.start()
        try:
            while True:
                got_message = asyncio.Future()
                log.info("Node {} is listening ...".format(zb.address))
                received_msg = await got_message
                reply = Message(sender=zb.address, content=received_msg.content)
                try:
                    await zb.unicast(message=reply, machine_name='sending_machine')
                except TransmissionError as exc:
                    log.exception(exc)
                log.info("Finished. Here is the message again:\n\t{}".format(received_msg.content.string))

        finally:
            zb.stop()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_update_others_1(self, event_loop):
        log.setLevel(logging.DEBUG)
        zb = ZigBeeConnector(event_loop, 'emasem01')
        await zb.start()
        try:
            await asyncio.sleep(1000)
        finally:
            zb.stop()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    @pytest.mark.asyncio
    async def test_update_others_2(self, event_loop):
        log.setLevel(logging.DEBUG)
        zb = ZigBeeConnector(event_loop, 'emasem02')
        await zb.start()
        try:
            await asyncio.sleep(1000)
        finally:
            zb.stop()
