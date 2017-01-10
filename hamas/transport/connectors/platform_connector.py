# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    06.10.2016
#   LICENSE:    MIT
#   FILE:	dummy_connector.py
# =============================================================================
"""Dummy interface for multiple dummy machines.

Dummy machines are machines which run on the same physical machine.
"""
import asyncio
import logging

from .connector import Connector

log = logging.getLogger(__name__)


class PlatformConnector(Connector):
    """Connector for agent communication on the same machine."""
    _machines = {}

    def __new__(cls, mts):
        """Initialize the interface with the creating machine.

        Args:
            mts (MessageTransportSystem): The calling MessageTransportSystem.

        """
        if mts.machine_name in cls._machines.keys():
            raise KeyError('The name {} is already taken'.format(
                mts.machine_name))
        cls._machines[mts.machine_name] = mts
        return super(PlatformConnector, cls).__new__(cls)

    def __del__(self):
        del self._machines[self.address]

    def __init__(self, mts):
        """Initialise the interface with the creating machine.

        Args:
            mts (MessageTransportSystem): The calling MessageTransportSystem.

        """
        super(PlatformConnector, self).__init__()
        self._message_transport = mts
        log.info("{} initialized with address {}.".format(self.__class__.__name__, self.address))

    def __contains__(self, machine_name):
        return machine_name in self.other_machines

    @property
    def other_machines(self):
        total = set(self._machines.keys())
        assert len(total) == len(self._machines)
        others = list(total.difference([self.address]))
        assert len(total) > len(others)
        return others

    async def unicast(self, machine_name, message):
        await self._machines[machine_name].receive(message)

    async def broadcast(self, message):
        others = self.other_machines

        futs = []
        for url in others:
            futs.append(asyncio.ensure_future(self.unicast(message=message, machine_name=url)))
        if futs:
            await asyncio.wait(futs)

    @property
    def address(self):
        return self._message_transport.machine_name
