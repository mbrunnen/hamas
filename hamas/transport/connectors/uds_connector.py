# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    01.12.2016
#   LICENSE:    MIT
#   FILE:       uds_connector.py
# =============================================================================
"""Connector for multiple unix platforms running in parallel
"""

import asyncio
import logging
import os

from .connector import Connector
from ..fractions import Fraction
from ..messages import Message
from ...exceptions import ConnectorError
from ...configuration import USE_UDS

log = logging.getLogger(__name__)


class UnixConnector(Connector):
    """Connector for agent communication on the same computer.

        Args:
            mts (MessageTransportSystem): The calling MessageTransportSystem.

    """

    def __init__(self, mts):
        super(UnixConnector, self).__init__()

        if not USE_UDS:
            raise ConnectorError(
                "Only available on Unix systems or is disabled.")
        self._address = None
        self._socket_dir = '/tmp/hamas_sockets/'
        self._address = self._socket_dir + mts.platform_name
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

    def __contains__(self, platform_name):
        """ The :class:`UnixConnector` implements a membership test.
        `platform_name in self` returns `True` if `platform_name` is a
        reachable address by using this connector :class:`UnixConnector` or
        `False` otherwise.
        """

        return platform_name in self.other_platforms

    def __del__(self):
        if self._address and os.path.exists(self._address):
            os.remove(self._address)

    async def start(self):
        self._server = await asyncio.start_unix_server(self._receive,
                                                       self._address)
        log.info("{} started.".format(self))
        self.started = True

    def stop(self):
        log.debug("Closing {}.".format(self))
        if self._server:
            self._server.close()

    @property
    def other_platforms(self):
        """list(str): Returns a list of addresses, which are reachable with
        the :class:`UnixConnector`.
        """
        total = set(os.listdir(self._socket_dir))
        others = list(total.difference([os.path.basename(self._address)]))
        return others

    @property
    def address(self):
        """str: The unique address of this connector.
        """
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
            log.info(
                "{} received a message {!r}".format(self._address, message))
            await self._mts.receive(message)

    async def unicast(self, platform_name, message):
        log.info("{} unicasts {!r}".format(self.__class__.__name__, message))
        serialized_msg = message.serialize()
        _, writer = await asyncio.open_unix_connection(
            os.path.join(self._socket_dir, platform_name))
        fractions = Fraction.disassemble(0, serialized_msg, self._mtu)
        lines = [f.serialize() for f in fractions]
        writer.writelines(lines)
        if writer.can_write_eof():
            writer.write_eof()
            await writer.drain()
            writer.close()

    async def broadcast(self, message):
        log.info("{} broadcasts {!r}".format(self.__class__.__name__, message))
        others = self.other_platforms
        futs = []
        for url in others:
            futs.append(
                asyncio.ensure_future(
                    self.unicast(message=message, platform_name=url)))
            if futs:
                await asyncio.wait(futs)
