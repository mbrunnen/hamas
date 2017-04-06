# -*- coding: utf-8 -*-
# ==============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    23.03.2017
#   LICENSE:    MIT
#   FILE:       mqtt_connector.py
# ==============================================================================
"""MQTT Connector

This module implements the communication over the MQTT Protocol.
"""

import asyncio
import logging
import os

import paho.mqtt.client as mqtt

from .connector import Connector
from ..messages import Message

log = logging.getLogger(__name__)


class MqttConnector(Connector):
    """ The :class:`MqttConnector`

        Args:
            mts (MessageTransportSystem): The calling MessageTransportSystem.
            broker (str): Address of the MQTT broker.
    """

    def __init__(self, mts, broker):
        # TODO: Add MQTT username and password
        super(MqttConnector, self).__init__()
        self._mts = mts
        self.client = mqtt.Client()
        self._address = mts.platform_name
        self.client.connect(broker, 1883, 60)
        self.client.on_connect = self._on_connect_cb
        self.client.on_message = self._on_message_cb
        self._connected = asyncio.Event()
        self._others = list()

    def __contains__(self, platform_name):
        return platform_name in self._others

    def _on_connect_cb(self, client, userdata, flags, rc):
        log.info("Connected via MQTT with result code %i.", rc)
        self.client.subscribe('others', qos=1)
        self.client.subscribe(self._address, qos=2)
        self.client.subscribe('broadcast', qos=0)
        self._connected.set()

    def _on_message_cb(self, client, userdata, msg):
        topic, subtopic = msg.topic.split('/')
        if topic == 'others':
            addr = str(msg.payload)
            if addr not in self._others:
                self._others.append(addr)
            if subtopic == 'request':
                self.client.publish('others/reply', self._address)
                self._connected.set()
            self._connected.set()

    def update_others(self):
        """Request other addresses
        """
        self.client.publish('others/request', self._address)

    def _register(self):
        """Register this platform in the MQTT network.
        """
        self.update_others()

    async def start(self):
        await self._connected.wait()

    def stop(self):
        log.debug("Closing {}.".format(self))
        self.client.disconnect()

    @property
    def other_platforms(self):
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
