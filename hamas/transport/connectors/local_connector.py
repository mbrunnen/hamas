# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    06.10.2016
#   LICENSE:    MIT
#   FILE:	local_connector.py
# =============================================================================
"""Communication interface for agents on the same machine.
"""

import asyncio


class LocalConnector(object):
    """Connector class for communication on the same machine.

    """

    def __init__(self, platform):
        """Constructor for LocalConnector"""
        super(LocalConnector, self).__init__()
        self._platform = platform

    def __contains__(self, url):
        return url in self.local_aids.keys()

    @property
    def local_aids(self):
        return self._platform.agents

    def other_agents(self, me):
        total = set(self.local_aids.keys())
        others = list(total.difference({me}))
        return others

    async def unicast(self, aid, message):
        await self.local_aids[aid].receive(message)

    async def broadcast(self, message):
        """

        Args:
            message:

        Raises:
            InterfaceError: Raises if the list of recipients is empty.

        """
        skip = message.sender
        aids = self.other_agents(skip)
        broadcast_futs = []
        for aid in aids:
            assert aid in self.local_aids.keys()
            broadcast_futs.append(
                asyncio.ensure_future(self.unicast(message=message,
                                                   aid=aid)))
        if broadcast_futs:
            await asyncio.wait(broadcast_futs)
