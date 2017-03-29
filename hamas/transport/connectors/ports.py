# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    26.10.2016
#   LICENSE:    MIT
#   FILE:       ports.py
# =============================================================================
"""
These are the TCP-like Ports. The ZigbeeConnector has the unicast ports 0-254
and the the broadcast port 255 respectively 0xff. The unicast ports have real
transmission control, whereas the broadcast port has no transmission control.
Enabling broadcasting on the transmission controlled ports would add a lot
of complexity and would make them potentially less reliable. Furthermore,
broadcasting is in our use case only for short messages and is considered
unreliable. It suffices if any other machine receives the message and it is
unnecessary to ensure that all other machines receive the broadcast. The
broadcast port is also used for network discovery, that means to map the
machine name to the ZigBee address. The unicast ports are implemented as
Moore automata, i.e. the outputs are defined by the states.
"""
import asyncio
import logging
import struct
import time

from ...exceptions import PortError, TransmissionError
from ..fractions import Fraction

log = logging.getLogger(__name__)


class Port(object):
    def __init__(self, number, zigbee_connector, timeout, mtu):
        self._number = number
        self._zigbee_connector = zigbee_connector
        self._timeout = timeout
        self._mtu = mtu

        # Transmission Control Block
        self._state = 'Closed'
        self.listening = asyncio.Event()
        self._transmission = None
        self._other_address = None
        self._message = None
        self._data_size = None
        self._outgoing_data = None
        self._incoming_data = None
        self._syn = None
        self._syn_ack = None
        self._data = None
        self._fin = None
        self._rst = None
        self._syn_time = None
        self._clear()

    @property
    def number(self):
        return self._number

    def __repr__(self):
        return "Port {} in state '{}'".format(self._number, self._state)

    def is_free(self):
        return self._state == 'Listen' or self._state == 'Closed'

    # The inputs:
    async def receive(self, source_address, fraction):
        log.debug("{} received {} from {}.".format(self, fraction, source_address))
        if fraction.flag == 'SYN':
            if self._state == 'Listen' and not self._syn.done():
                self._syn.set_result((source_address, fraction))
            elif source_address != self._other_address:
                await self._deny(source_address)
            else:
                log.info("Port {:d} drops {} with ID {:d} from {}.".format(self.number, fraction.flag, fraction.seq_id, source_address))
        elif source_address == self._other_address:
            if fraction.flag == 'SYN-ACK' and not self._syn_ack.done():
                self._syn_ack.set_result(fraction)
            elif fraction.flag == 'DATA':
                self._data.put_nowait(fraction)
            elif fraction.flag == 'FIN' and not self._fin.done():
                self._fin.set_result(fraction)
            elif fraction.flag == 'RST' and not self._rst.done():
                self._rst.set_result(fraction)
            else:
                log.info("Port {:d} drops {} with ID {:d} from {}.".format(self.number, fraction.flag, fraction.seq_id, source_address))
        else:
            log.warning("Port {:d} drops {} with ID {:d} from unknown address {}.".format(self.number, fraction.flag, fraction.seq_id, source_address))

    async def open(self):
        """ Open the port so it's listening.
        """
        if self._state == 'Closed':
            self._transmission = asyncio.ensure_future(self._listen())
            await self.listening.wait()
        else:
            raise PortError("Port {} is in use".format(self))

    def _reopen(self):
        self._clear()
        self._state = 'Listen'
        self._transmission = asyncio.ensure_future(self._listen())

    async def close(self):
        """Close the port nicely.

        Setting the port to the initial state, by waiting for the transmission to finish.
        In the closed state are no pending coroutines.
        """
        await self.listening.wait()
        assert not self._syn.done()
        self._syn.set_result('close')
        await self._transmission
        self._state = 'Closed'
        self._clear()
        log.debug("{} is now closed.".format(self))

    def stop(self):
        """Stop running coroutines.
        """
        if self._transmission is not None:
            self._transmission.cancel()
        self._clear()
        self._state = 'Closed'
        log.debug("{} is closed and stopped.".format(self))

    async def send(self, dest_address, message):
        """ Open the port for sending a message.
        Args:
            dest_address (str): The zigbee address of the receiver.
            message (bytes): The message to be send.

        Raises:
            TransmissionError: When the port is in use or an error while sending occurred.
        """
        self._other_address = dest_address
        self._message = message
        if self._state == 'Closed':
            self._transmission = asyncio.ensure_future(self._syn_sent())
            await self._transmission
        elif self._state == 'Listen' and not self._syn.done():
            self._syn.set_result('send')
            await self._transmission
        else:
            raise PortError("Port {} is in use".format(self))

    def _clear(self):
        self.listening.clear()
        self._transmission = None
        self._other_address = None
        self._message = None
        self._data_size = None
        self._outgoing_data = []
        self._incoming_data = []
        self._syn = asyncio.Future()
        self._syn_ack = asyncio.Future()
        self._data = asyncio.Queue()
        self._fin = asyncio.Future()
        self._rst = asyncio.Future()
        self._syn_time = None

    # States:
    async def _listen(self):
        self._state = 'Listen'
        self.listening.set()
        log.debug("{} is now listening.".format(self))
        syn = await self._syn
        self.listening.clear()
        if type(syn) is tuple:
            await self._syn_received(*syn)
        elif syn == 'send':
            await self._syn_sent()

    async def _syn_sent(self):
        """Checking if the other port accepts data and send the size of the data

        Raises:
            PortError: When the other Port is occupied, try another Port.
            TransmissionError: Transmission failed.
        """

        self._state = 'SYN-sent'

        self._outgoing_data = Fraction.disassemble(self._number, self._message, self._mtu)
        size = struct.pack('>I', len(self._outgoing_data))
        syn = Fraction(self._number, 'SYN', sdu=size)

        pending_responses = [self._rst, self._syn_ack]
        # self._syn_ack = asyncio.Future()

        try:
            await self._zigbee_connector.send_fraction(self._other_address, syn)
            for frac_fut in asyncio.as_completed(pending_responses, timeout=self._timeout):
                response = await frac_fut
                if response.flag == 'SYN-ACK':
                    log.debug("Port {} got a valid SYN-ACK.".format(self))
                    break
                else:
                    self._reopen()
                    raise PortError("{} send a SYN, but the other port sent a RST.".format(self))
        except asyncio.TimeoutError:
            self._reopen()
            raise TransmissionError("{} did not get a response to a SYN.".format(self))
        except TransmissionError as exc:
            self._reopen()
            raise exc
        else:
            await self._sending()

    async def _sending(self):
        self._state = 'Sending'
        log.info("%s is sending a message with %i DATA fractions and %i bytes.", self, len(self._outgoing_data), len(self._message))
        try:
            await self._send_data()
        except TransmissionError as exc:
            self._reopen()
            raise exc
        await self._sent()

    async def _sent(self):
        self._state = 'Sent'
        pending_responses = [self._rst, self._fin]
        try:
            for frac_fut in asyncio.as_completed(pending_responses, timeout=self._timeout):
                response = await frac_fut
                if response.flag == 'FIN':
                    log.debug("{} successfully transmitted the message.".format(self))
                else:
                    raise TransmissionError("{} send data but the receiving port got corrupted data.".format(self))
                break
        except asyncio.TimeoutError:
            raise TransmissionError("{} didn't get any response.".format(self))
        finally:
            self._reopen()

    async def _syn_received(self, other_address, syn):
        self._state = 'SYN-received'
        self._syn_time = time.monotonic()
        self._other_address = other_address
        self._data_size, = struct.unpack('>I', syn.sdu)

        synack = Fraction(self._number, 'SYN-ACK')

        try:
            await self._zigbee_connector.send_fraction(self._other_address, synack)
        except TransmissionError as exc:
            log.exception(exc)
            self._reopen()
        else:
            await self._receiving()

    async def _receiving(self):
        self._state = 'Receiving'
        log.debug("%s is now receiving.", self)

        start = time.monotonic()
        while len(self._incoming_data) < self._data_size:
            try:
                data = await asyncio.wait_for(self._data.get(), self._timeout)
            except asyncio.TimeoutError:
                dur = time.monotonic() - start
                log.error("%s reached a timeout after %f seconds. Collected %i from %i fraction.",
                          self, dur, len(self._incoming_data), self._data_size)
                await self._deny(self._other_address)
                self._reopen()
                return
            else:
                self._add_data(data)
                self._data.task_done()
        frac_num = len(self._incoming_data)
        log.info("%s received %i fractions.", self, frac_num)

        await self._received()

    async def _received(self):
        self._state = 'Received'
        fin = Fraction(self._number, 'FIN')

        try:
            assert len(self._incoming_data) == self._data_size
            serialized_message = Fraction.assemble_msg(self._incoming_data)
            self._zigbee_connector.deliver(serialized_message)
            await self._zigbee_connector.send_fraction(self._other_address, fin)
        except Exception as exc:
            await self._deny(self._other_address)
            log.exception(exc)
        finally:
            self._reopen()

    # Output:
    async def _deny(self, address):
        frac = Fraction(
            port=self._number,
            flag='RST')
        try:
            await self._zigbee_connector.send_fraction(address, frac)
        except TransmissionError as exc:
            log.exception(exc)

    async def _send_data(self):
        for f in self._outgoing_data:
            await self._zigbee_connector.send_fraction(self._other_address, f)

    # Helper
    def _add_data(self, data):
        if data.seq_id not in [f.seq_id for f in self._incoming_data]:
            self._incoming_data.append(data)
        else:
            log.info("Port {} got a duplicate data fraction with ID {:d} from {}.".format(self.number, data.seq_id, data.port))
