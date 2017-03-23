# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    26.09.2016
#   LICENSE:    MIT
#   FILE:       local_connector.py
# =============================================================================
""" Connector to control to XBee-ZigBee modules.

This corresponds to the data link layer in the OSI model. Frames are sent from
one node to another. Multiple frames can be part of one message. The purpose
of this module is to fragment messages in fractions, regarding the MTU,
and to send them. Also received frames will be assembled to a message and be
delivered to the machine. Another Function will be a integrity
check.
"""

import asyncio
import importlib
import logging
import os
import random
import struct
import time

import serial
import serial.tools.list_ports
from xbee import ZigBee

from hamas.exceptions import ConnectorError, TransmissionError, PortError
from hamas.transport.fractions import Fraction
from hamas.transport.messages import Message
from hamas.transport.serializable import Serializable
from hamas.utils import hexstr2bytes, bytes2hexstr
from .connector import Connector
from .ports import Port

NOZIGBEE = 'HAMASNOZIGBEE' in os.environ.keys() and os.environ['HAMASNOZIGBEE'] == '1'
log = logging.getLogger(__name__)


class ZigBeeConnector(Connector):
    """Class which wraps the ZigBee class in the xbee package.

    Attributes:
        _serial(Serial): Serial communication port.
        _loop(BaseEventLoop): Asyncio event loop.
        _zigbee(ZigBee): The XBee module with ZigBee functionality.
        _response_futs(dict): The futures handling incoming response frames
        _serial_timeout(float): Time that will be waited for another frame from the xbee module to arrive.
        _unicast_timeout (float): Time that will be waited for another fraction to arrive
    """

    def __init__(self, loop,
                 machine_name,
                 regex='/dev/ttyUSB',
                 baud=230400,
                 callback=None,
                 serial_timeout=5,
                 ucast_timeout=5):
        super(ZigBeeConnector, self).__init__()
        ports = [fd for fd, p, i in serial.tools.list_ports.grep(regex)]
        if NOZIGBEE:
            raise (ConnectorError('ZigBee is disabled.'))
        if len(ports) == 0:
            raise ConnectorError('No serial device found.')

        if len(ports) > 1:
            raise ConnectorError(
                'Too many serial devices found, cannot determine'
                'which is the ZigBee module.')

        self._serial = serial.Serial(ports[0], baud)

        def read_address():
            log.info("Initialize ZigBee module...")
            temp_zigbee = ZigBee(self._serial)
            try:
                commands = {'hi': b'SH', 'lo': b'SL', 'my': b'MY'}
                responses = {}
                for k, c in commands.items():
                    temp_zigbee.at(command=c)
                    frame = temp_zigbee.wait_read_frame()
                    try:
                        responses[k] = frame['parameter']
                    except KeyError as exc:
                        msg = "The initialisation of the ZigBee module went wrong. " \
                              "No 'parameter' key found:\n\t{}".format(frame)
                        log.exception(msg)
                        raise exc

            except KeyboardInterrupt:
                temp_zigbee.halt()
                raise ConnectorError("The user interrupted the initialisation of the ZigBeeConnector.")
            else:
                return self.compose_address(b''.join([responses['hi'], responses['lo']]), responses['my'])

        self._address = read_address()
        self._loop = loop
        # how many fractions can be sent in parallel
        self._send_queue = asyncio.Queue(maxsize=4)
        self._send_task = None
        self._response_futs = {}
        self._serial_timeout = serial_timeout
        self._unicast_timeout = ucast_timeout
        self._mtu = 84
        # TODO: Better to pass the MTS, callback is not necessary.
        # callback is not a coro, because of functools
        assert not callback or (not asyncio.iscoroutinefunction(callback))
        self._callback = callback
        self._zigbee = ZigBee(self._serial, callback=self._receive_cb)
        self._other_machines = {}
        self._joined = asyncio.Event()
        self._ports_opened = asyncio.Event()
        self._current_frame_id = 0
        self._current_fraction_id = 0
        # For network discovery the machine name has to fit in one fraction
        assert len(machine_name) <= Fraction.max_sdu_len(self._mtu), "The machine name is too long"
        self._machine_name = machine_name
        self._ports = [Port(i, self, ucast_timeout, self._mtu) for i in range(Fraction.max_ports() - 1)]
        log.info("{} initialised with address {}.".format(self.__class__.__name__, self._address))

    def __contains__(self, machine_url):
        return machine_url in self._other_machines.keys()

    @property
    def mtu(self):
        return self._mtu

    @property
    def address(self):
        return self._address

    @property
    def machine_name(self):
        return self._machine_name

    def _generate_frame_id(self):
        """Create an approximately unique frame ID between 1-255.

        Only if an Frame ID is set and is not zero, the xbee module will send
        an feedback frame.
        """
        max_count = 2 ** (8 * struct.calcsize('B')) - 1
        self._current_frame_id = (self._current_frame_id % max_count) + 1
        fid = bytes([self._current_frame_id])
        return fid

    def _get_port(self):
        port_numbers = list(range(len(self._ports)))
        random.shuffle(port_numbers)
        for n in port_numbers:
            if self._ports[n].is_free():
                yield self._ports[n]

    async def send_fraction(self, address, fraction):
        """ Send a message with low level transmission control

        Args:
            address (str): The recipient's address
            fraction (Fraction): The fraction to be transmitted
        """
        start = time.monotonic()
        serialized_frac = fraction.serialize()
        response = await self.send_command(cmd='tx',
                                           address=address,
                                           data=serialized_frac)
        if response['deliver_status'] != b'\x00':
            raise TransmissionError('The transmission failed with status "0x{}".'.format(bytes2hexstr(response['deliver_status'])))
        log.info("Sent a %s fraction to port %i on %s.", fraction.flag, fraction.port, address,
                 extra={'data_context': 'sent_frac',
                        'data': {
                            'frac_type': fraction.flag,
                            'dest_addr': address,
                            'port': fraction.port,
                            'seq_id': fraction.seq_id,
                            'bytes': len(serialized_frac),
                            'dur': time.monotonic() - start
                        }
                        })

    async def broadcast_fraction(self, fraction, hops=None):
        log.info("Broadcasting a {} fraction.".format(fraction.flag))
        response = await self.send_command(cmd='tx',
                                           address='00:00:00:00:00:00:FF:FF!FFFE',
                                           data=fraction.serialize(),
                                           broadcastradius=hops)
        if response['deliver_status'] != b'\x00':
            raise TransmissionError('The transmission failed with status "0x{}".'.format(bytes2hexstr(response['deliver_status'])))

    async def send_command(self, address=None, **kwargs):
        """ Send a zigbee related AT command

        Supported AT commands are for example ND (Network discovery) and NP (Maximum payload size per frame in bytes).

        Args:
            address(str): For example 'DE:AD:BE:EF:42:00:00:00!EF:42' or 'DE:AD:BE:EF:42:00:00:00'
                the module does not response in time.

        Returns:
            response(dict): The response of the XBee module with e.g. the transmission status.

        """
        assert self._send_task is not None and not self._send_task.done()
        if address:
            long_address, short_address = self.parse_address(address)
        else:
            long_address = None
            short_address = None

        frame_id = self._generate_frame_id()

        pending_response = asyncio.Future()
        self._response_futs[frame_id] = pending_response

        kwargs['dest_addr'] = short_address
        kwargs['dest_addr_long'] = long_address
        kwargs['frame_id'] = frame_id

        await self._send_queue.put((pending_response, kwargs))

        try:
            response = await pending_response
        except asyncio.TimeoutError as exc:
            raise TransmissionError("The transmission failed without response.") from exc
        else:
            return response
        finally:
            self._response_futs.pop(frame_id)

    async def _send_handler(self):
        while True:
            pending_response, send_kwargs = await self._send_queue.get()
            log.debug("ZigBee is sending...")
            self._zigbee.send(**send_kwargs)
            try:
                await asyncio.wait_for(pending_response, self._serial_timeout)
            except asyncio.TimeoutError:
                log.error("Send did not get a response.")
            finally:
                self._send_queue.task_done()

    def _receive_cb(self, data):
        """XBee callback function for new messages.

        This method is called by another thread, than the main thread
        where the event loop resides. To use the message futures in the
        event loop, we have to set the results of the futures in the
        same thread as the event loop, the main thread. Therefore, the data must be passed to the event loop in
        the main thread. This is done by using the run_coroutine_threadsafe method.

        """
        asyncio.run_coroutine_threadsafe(self._frame_received(data), self._loop)

    async def _frame_received(self, frame):
        """Appending new messages.

        This method is called when frame arrives. It will simply distribute the frame to the right queue. If no queue
        with the same frame ID exists, it will be created. The method should be called thread-safe, that means it is in
        the same thread as the event loop, the main thread.

        Args:
            frame(dict): The arriving frame.

        """

        log.debug("Got a new frame.")

        if 'frame_id' not in frame.keys():
            # New Fraction received
            api_id = frame['id']
            if api_id == 'rx' or api_id == 'rx_explicit':
                assert 'rf_data' in frame.keys()
                address = self.compose_address(frame['source_addr_long'], frame['source_addr'])
                fraction = frame['rf_data']
                self._fraction_received(fraction, address)
            else:
                log.warning('Got a frame with unexpected API ID "{}":\n\t{}'.format(api_id, frame))
        else:
            frame_id = frame['frame_id']
            if frame_id in self._response_futs:
                if self._response_futs[frame_id].done():
                    log.warning("Got a frame for a done Future.")
                else:
                    await self._response_futs[frame_id].set_result(frame)

    def _fraction_received(self, serialized_frac, source_address):
        fraction = Fraction.deserialize(serialized_frac)
        if fraction.port == 0xff and (fraction.flag == 'URL' or fraction.flag == 'JOIN'):
            asyncio.ensure_future(self._add_machine(source_address, fraction))
        else:
            asyncio.ensure_future(self._ports[fraction.port].receive(source_address, fraction))

        log.info("Received a %s fraction from %s for port %i.", fraction.flag, source_address, fraction.port,
                 extra={'data_context': 'received_frac',
                        'data': {
                            'frac_type': fraction.flag,
                            'source_addr': source_address,
                            'port': fraction.port,
                            'seq_id': fraction.seq_id,
                            'bytes': len(serialized_frac),
                        }
                        })

    def deliver(self, serialized_message):
        log.debug("Got a new serialized Message with {:d} bytes.".format(len(serialized_message)))
        try:
            message = self._deserialize_message(serialized_message)
        except (KeyError, EOFError, ValueError, TypeError):
            log.exception("Deserialization of the message %s went wrong.", serialized_message)
        else:
            if self._callback:
                self._callback(message)
            else:
                log.warning("No callback provided. Throwing away message:\n\t".format(message))

    @staticmethod
    def _deserialize_message(serialized_msg):
        code, = struct.unpack('c', serialized_msg[0:1])

        serializer = Serializable.serializers[code]
        path, class_name = serializer.rsplit('.', 1)
        module = importlib.import_module(path)
        serializable = getattr(module, class_name)
        assert issubclass(serializable, Serializable)
        message = serializable.deserialize(serialized_msg)
        return message

    async def update_others(self):
        """ Get the other participants in the network.

        """
        frac = Fraction(
            port=0xff,
            flag='JOIN',
            sdu=self.machine_name.encode())
        await self.broadcast_fraction(frac)

    async def _add_machine(self, source_address, fraction):
        source_machine_name = fraction.sdu.decode()
        if fraction.flag == 'JOIN':
            # passive add
            log.info("Added machine '{}' with address {}.".format(source_machine_name, source_address))
            self._other_machines[source_machine_name] = source_address
            response = Fraction(0xff, flag='URL', sdu=self._machine_name.encode())
            await self._ports_opened.wait()
            await self.send_fraction(source_address, response)
            self._joined.set()
        elif fraction.flag == 'URL':
            # active add
            self._other_machines[source_machine_name] = source_address
            self._joined.set()
        else:
            log.warning("Got a {} fraction on reserved port 255 from {}.".format(fraction.flag, source_address))

    async def wait_for_others(self):
        log.info("Waiting for other machines...")
        await self._joined.wait()
        self._joined.clear()

    @property
    def other_machines(self):
        return list(self._other_machines.keys())

    async def unicast(self, machine_name, message):
        """

        Args:
            machine_name:
            message:

        Raises:
            TransmissionError: When every port unavailable or the transmission failed, an error is thrown.

        """
        start = time.monotonic()
        assert type(message) is Message
        address = self._other_machines[machine_name]
        serialized = message.serialize()
        for port in self._get_port():
            try:
                await port.send(address, serialized)
            except PortError as exc:
                log.warning("Transmission on %s not possible: %s", port, exc.message)
            else:
                log.info("Transmitted a message on %s.", port,
                         extra={'data_context': 'zigbee_sent_msgs',
                                'data': {
                                    'performative': message.performative,
                                    'sender': message.sender,
                                    'routing': message.routing,
                                    'recipient': message.recipient,
                                    'dest_addr': address,
                                    'content': message.content.__class__.__name__,
                                    'conversation_id': '0x' + bytes2hexstr(message.conversation_id),
                                    'management': self._machine_name,
                                    'port': port.number,
                                    'bytes': len(serialized),
                                    'duration': time.monotonic() - start,
                                    'frac_num': Fraction.num_fractions(serialized, self._mtu),
                                }
                                })
                return

        raise TransmissionError("Transmission failed on all Ports.")

    async def broadcast(self, message):
        assert type(message) is Message

        futs = []
        for m in self.other_machines:
            futs.append(asyncio.ensure_future(self.unicast(message=message, machine_name=m)))
        if futs:
            await asyncio.wait(futs)

    async def open_ports(self):
        await asyncio.wait([asyncio.ensure_future(p.open()) for p in self._ports])

    async def close_ports(self):
        await asyncio.wait([asyncio.ensure_future(p.close()) for p in self._ports])

    async def start(self):
        """ Start the ZigBeeConnector

        Start the send queue handler and make a network discovery.
        """
        if self._send_task is not None:
            assert self._send_task.done()
        self._send_task = asyncio.ensure_future(self._send_handler())
        await self.open_ports()
        self._ports_opened.set()
        await self.update_others()

    def stop(self):
        """ Cancel running coroutines.
        """
        self._zigbee.halt()
        self._serial.close()
        for p in self._ports:
            p.stop()
        if self._send_task is not None:
            self._send_task.cancel()
        log.info("ZigbeeConnector stopped.")

    @staticmethod
    def compose_address(long_address, short_address=None):
        """Convert the addresses, readable by xbee to a uniform form

        Args:
            long_address: A 8 byte long byte string, e.g. b'\xde\xad\xbe\xef\x42\x00\x00\x00'
            short_address: A 2 byte long byte string, e.g. b'\xef\x42'

        Returns:
            address_string: For example 'DE:AD:BE:EF:42:00:00:00!EF:42'

        """
        address_string = ':'.join(["{:02X}".format(x) for x in long_address])
        if short_address:
            address_string += '!' + "{:02X}{:02X}".format(short_address[0], short_address[1])
        return address_string

    @classmethod
    def parse_address(cls, address_string):
        long_addr, _, short_addr = address_string.partition('!')
        long_addr = ''.join(long_addr.split(':'))
        long_addr = hexstr2bytes(long_addr)
        if not short_addr:
            short_addr = b'\xFF\xFE'
        else:
            short_addr = hexstr2bytes(short_addr)
        assert len(long_addr) == 8
        assert len(short_addr) == 2
        return long_addr, short_addr
