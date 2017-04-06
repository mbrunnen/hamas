# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    06.10.2016
#   LICENSE:    MIT
#   FILE:	    platform_connector.py
# =============================================================================
"""Connector for multiple logical platforms on one physical machine.
"""

import asyncio
import logging

from .connector import Connector

log = logging.getLogger(__name__)


class PlatformConnector(Connector):
    """Connector for connecting multiple agent platforms on the same physical machine.
        Args:
            mts (MessageTransportSystem): The calling MessageTransportSystem.
    """
    _platforms = {}

    def __new__(cls, mts):
        if mts.platform_name in cls._platforms.keys():
            raise KeyError(
                'The name {} is already taken'.format(mts.platform_name))
        cls._platforms[mts.platform_name] = mts
        return super(PlatformConnector, cls).__new__(cls)

    def __del__(self):
        del self._platforms[self.address]

    def __init__(self, mts):
        super(PlatformConnector, self).__init__()
        self._message_transport = mts
        log.info("{} initialized with address {}.".format(
            self.__class__.__name__, self.address))

    def __contains__(self, platform_name):
        return platform_name in self.other_platforms

    @property
    def other_platforms(self):
        total = set(self._platforms.keys())
        assert len(total) == len(self._platforms)
        others = list(total.difference([self.address]))
        assert len(total) > len(others)
        return others

    async def unicast(self, platform_name, message):
        await self._platforms[platform_name].receive(message)

    async def broadcast(self, message):
        others = self.other_platforms

        futs = []
        for url in others:
            futs.append(
                asyncio.ensure_future(
                    self.unicast(message=message, platform_name=url)))
        if futs:
            await asyncio.wait(futs)

    @property
    def address(self):
        return self._message_transport.platform_name
