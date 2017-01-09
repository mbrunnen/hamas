# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    01.12.2016
#   LICENSE:    MIT
#   FILE:       unix_connector.py
# =============================================================================
"""Connector for multiple unix platforms running in parallel
"""

import asyncio
import logging
import os

from hamas.exceptions import ConnectorError
from hamas.transport.fractions import Fraction
from hamas.transport.messages import Message
from .connector import Connector

log = logging.getLogger(__name__)

UDS = 'HAMASUDS' in os.environ.keys() and os.environ['HAMASUDS'] == '1'


class UnixConnector(Connector):
    """Connector for agent communication on the same computer."""

    def __init__(self, mts):
        """Initialise the interface with the creating machine.

        Args:
            mts (MessageTransportSystem): The calling MessageTransportSystem.

        """
        super(UnixConnector, self).__init__()

        if not os.name == 'posix' or not UDS:
            self._address = None
            raise ConnectorError("Only available on Unix systems or is disabled.")
        self._socket_dir = '/tmp/hamas_sockets/'
        self._address = self._socket_dir + mts.machine_name
        self._mtu = 1024
        self._mts = mts
        os.makedirs(self._socket_dir, exist_ok=True)

        try:
            os.unlink(self._address)
        except OSError:
            if os.path.exists(self._address):
                raise
        self._server = None
        log.info("{} initialised.".format(self))

    def __contains__(self, machine_name):
        return machine_name in self.other_machines

    def __del__(self):
        if self._address and os.path.exists(self._address):
            os.remove(self._address)

    async def start(self):
        self._server = await asyncio.start_unix_server(self._receive, self._address)
        log.info("{} started.".format(self))
        self.started = True

    def stop(self):
        log.debug("Closing {}.".format(self))
        if self._server:
            self._server.close()

    @property
    def other_machines(self):
        total = set(os.listdir(self._socket_dir))
        others = list(total.difference([os.path.basename(self._address)]))
        return others

    @property
    def address(self):
        return self._address

    async def _receive(self, reader, writer):

        fractions = []
        while True:
            data = await reader.read(self._mtu)
            if data:
                log.debug("{} received {!r}".format(self, data))
                fractions.append(Fraction.deserialize(data))
            else:
                log.debug("Closing {}".format(self))
                break
            await writer.drain()
        writer.close()
        serialized_msg = Fraction.assemble_msg(fractions)
        message = Message.deserialize(serialized_msg)
        log.info("{} received a message {!r}".format(self._address, message))
        await self._mts.receive(message)

    async def unicast(self, machine_name, message):
        log.info("{} unicasts {!r}".format(self.__class__.__name__, message))
        serialized_msg = message.serialize()
        _, writer = await asyncio.open_unix_connection(os.path.join(self._socket_dir, machine_name))
        fractions = Fraction.disassemble(0, serialized_msg, self._mtu)
        lines = [f.serialize() for f in fractions]
        writer.writelines(lines)
        if writer.can_write_eof():
            writer.write_eof()
        await writer.drain()
        writer.close()

    async def broadcast(self, message):
        log.info("{} broadcasts {!r}".format(self.__class__.__name__, message))
        others = self.other_machines
        futs = []
        for url in others:
            futs.append(asyncio.ensure_future(self.unicast(message=message, machine_name=url)))
        if futs:
            await asyncio.wait(futs)
