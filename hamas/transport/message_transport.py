# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    18.08.2016
#   LICENSE:    MIT
#   FILE:       message_transport.py
# =============================================================================

import asyncio
import logging

from .connectors.local_connector import LocalConnector
from .connectors.platform_connector import PlatformConnector
from .connectors.unix_connector import UnixConnector
from .connectors.zigbee_connector import ZigBeeConnector
from .messages import Message
from ..exceptions import TransmissionError, ConnectorError
from ..utils import bytes2hexstr

log = logging.getLogger(__name__)


class MessageTransportSystem(object):
    """Provides the communication between agents.

    Args:
        self._platform(AgentPlatform)
    """

    def __init__(self, platform, update_interval=60, regex='/dev/ttyUSB'):
        """TODO: to be defined.
        """

        self._platform = platform
        self._loop = platform.loop
        self._pending_reply_futs = {}
        self._broadcast_replies = {}
        self._send_timeout = 5
        self._reply_timeout = 5
        self._running = False
        self._interval = update_interval
        self._run_task = None
        self._local_connector = LocalConnector(self._platform)
        self._platform_connector = None
        self._unix_connector = None
        self._zigbee_connector = None
        self._initiate_connectors(regex)

    # def __del__(self):
    #     if self._platform_connector:
    #         del self._platform_connector
    #     if self._unix_connector:
    #         del self._unix_connector
    #     if self._local_connector:
    #         del self._local_connector
    #     if self._zigbee_connector:
    #         del self._zigbee_connector


    @property
    def platform_name(self):
        return self._platform.name

    @property
    def loop(self):
        return self._loop

    async def send(self, message):
        """This method checks the routing option.

        This is a coroutine because it has to wait for the xbee module in
        another thread.
        """
        assert type(
            message) is Message, "Only Messages can be sent:\n\t".format(
            message)
        log.debug(
            "Sending a message from {} to {} via {}.".format(message.sender,
                                                             message.recipient,
                                                             message.routing))
        if message.sender == message.recipient:
            raise TransmissionError(
                'Agent "{}" wants to send a message to himself.'.format(
                    message.sender))

        if message.routing == 'unicast':
            await self._unicast(message, message.recipient)
        elif message.routing == 'broadcast':
            await self._broadcast(message)
        else:
            raise NotImplementedError(
                "Routing mode %s is not implemented yet." % message.routing)

    async def _unicast(self, message, recipient):
        """ Send a message to one specific agent.
        """
        assert type(recipient) is str
        p_name, a_name = self.parse_aid(recipient)
        if recipient in self._local_connector:
            await self._local_connector.unicast(message=message, aid=recipient)
        elif self._platform_connector and p_name in self._platform_connector:
            await self._platform_connector.unicast(message=message,
                                                   platform_name=p_name)
        elif self._unix_connector and p_name in self._unix_connector:
            await self._unix_connector.unicast(message=message,
                                               platform_name=p_name)
        elif self._zigbee_connector and p_name in self._zigbee_connector:
            await self._zigbee_connector.unicast(message=message,
                                                 platform_name=p_name)
        else:
            raise TransmissionError(
                "Transmission to agent {} on platform {} failed.".format(a_name,
                                                                        p_name))

    async def _broadcast(self, message):
        assert message.recipient is None
        broadcast_jobs = list()

        p_name, aid = self.parse_aid(message.sender)
        broadcast_jobs.append(
            asyncio.ensure_future(self._local_connector.broadcast(message)))
        # don't rebroadcast
        if p_name == self.platform_name:
            if self._platform_connector:
                broadcast_jobs.append(
                    asyncio.ensure_future(
                        self._platform_connector.broadcast(message)))
            if self._unix_connector:
                broadcast_jobs.append(
                    asyncio.ensure_future(
                        self._unix_connector.broadcast(message)))
            if self._zigbee_connector:
                broadcast_jobs.append(
                    asyncio.ensure_future(
                        self._zigbee_connector.broadcast(message)))

        await asyncio.wait(broadcast_jobs)

    def _sync_receive(self, message):
        asyncio.ensure_future(self.receive(message))

    async def receive(self, message):
        # sender = message.sender
        # recipient = message.sender
        # if sender in self._local_connector:
        #     sender_type
        # else:

        log.info(
            "MessageTransportSystem received a %s message from %s for %s with content %s.",
            message.routing, message.sender, message.recipient,
            message.content.__class__.__name__,
            extra={'data_context': 'received_msgs',
                   'data': {'performative': message.performative,
                            'sender': message.sender,
                            'routing': message.routing,
                            'recipient': message.recipient,
                            'content': message.content.__class__.__name__,
                            'conversation_id': '0x' + bytes2hexstr(
                                message.conversation_id),
                            'management': self._platform_name}})
        await self.send(message)

    @classmethod
    def parse_aid(cls, aid):
        try:
            platform_name, _, agent_name = aid.partition('/')
            assert platform_name, 'No platform name specified.'
        except AssertionError as exception:
            raise ValueError(
                'Cannot parse AID "{}":\n\t {}'.format(aid, exception))

        return platform_name, agent_name

    async def start(self):
        if self._unix_connector:
            await self._unix_connector.start()
        if self._zigbee_connector:
            await self._zigbee_connector.start()

        if not self._running:
            self._running = True
            self._run_task = asyncio.ensure_future(self._run())

    def stop(self):
        if self._running:
            self._running = False
            self._run_task.cancel()
        if self._unix_connector:
            self._unix_connector.stop()
        if self._zigbee_connector:
            self._zigbee_connector.stop()

    async def wait_for_zigbee(self):
        await self._zigbee_connector.wait_for_others()

    async def _run(self):
        while self._running:
            await asyncio.sleep(self._interval)
            log.info(
                "The MessageTransportSystem on '{}' ran an update task.".format(
                    self._platform_name))
            await self._zigbee_connector.update_others()

    @property
    def other_platforms(self):
        others = list()
        if self._platform_connector:
            others += self._platform_connector.other_platforms
        if self._unix_connector:
            others += self._unix_connector.other_platforms
        if self._zigbee_connector:
            others += self._zigbee_connector.other_platforms
        return others

    def _initiate_connectors(self, regex):
        """Initiate communication channels.
        """
        try:
            self._platform_connector = PlatformConnector(self)
        except ConnectorError:
            self._platform_connector = None
            log.warning("Could not initialize PlatformConnector.")
        try:
            self._unix_connector = UnixConnector(self)
        except ConnectorError:
            self._unix_connector = None
            log.warning("Could not initialize UnixConnector.")
        try:
            self._zigbee_connector = ZigBeeConnector(self._loop,
                                                     platform_name=self.platform_name,
                                                     callback=self._sync_receive,
                                                     regex=regex)
        except ConnectorError:
            self._zigbee_connector = None
            log.warning("Could not initialize ZigBeeConnector.")
