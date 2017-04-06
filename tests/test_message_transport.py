# -*- coding: utf-8 -*-
# ==============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    14.07.2016
#   LICENSE:    MIT
#   FILE:	    test_message_transport.py
# ==============================================================================
"""Tests for the MessageTransportSystem class.
"""

import asyncio
import logging
import os

import pytest
import serial.tools.list_ports

from hamas import Agent, MessageTransportSystem, Message, provide, StringContent, AgentPlatform

log = logging.getLogger(__name__)

TESTNOZIGBEE = 'HAMASNOZIGBEE' in os.environ.keys() and os.environ['HAMASNOZIGBEE'] == '1'
TESTNOTCONNECTED = not [fd for fd, p, i in serial.tools.list_ports.grep('/dev/ttyUSB')] and not TESTNOZIGBEE
TESTZIGBEE = not TESTNOZIGBEE and not TESTNOTCONNECTED
log.setLevel(logging.DEBUG)


class TestMessageTransport:
    """Test for the agent class
    """

    @pytest.mark.asyncio
    async def test_communication(self, ap):
        """Test if an agent call call an others agent method
        """

        class MyAgent(Agent):
            """Docstring for MyAgent. """

            def __init__(self, text, *args, **kwargs):
                super(MyAgent, self).__init__(*args, **kwargs)
                self.text = text

            async def receive(self, message):
                assert self.aid == message.recipient
                assert self.aid != message.sender
                self.text = message.content.string

        message_text1 = "this should be in agent 2 after sending."
        message_text2 = "this should be in agent 1 after sending."

        agent1 = ap.create_agent(MyAgent, text=message_text1)
        agent2 = ap.create_agent(MyAgent, text=message_text2)

        message1 = Message(sender=agent1.aid, content=StringContent(agent1.text), recipient=agent2.aid)
        message2 = Message(sender=agent2.aid, content=StringContent(agent2.text), recipient=agent1.aid)

        assert agent1.text == message_text1
        assert agent2.text == message_text2
        assert agent1.text != agent2.text

        await agent1.send(message1)
        assert agent2.text == message_text1

        await agent2.send(message2)
        assert agent1.text == message_text2

    @pytest.mark.asyncio
    async def test_broadcast(self, ap):
        """Test if an agent call call an others agent method
        """

        class MyAgent(Agent):
            def __init__(self, text='', *args, **kwargs):
                super(MyAgent, self).__init__(*args, **kwargs)
                self.text = text

            async def receive(self, message):
                self.text = message.content.string

        message_text = "send this from agent 1 to all others"

        sender = ap.create_agent(MyAgent, text=message_text)
        receivers = [ap.create_agent(MyAgent) for _ in range(2, 5)]

        message = Message(sender=sender.aid, content=StringContent(message_text),
                          routing='broadcast')

        assert sender.text == message_text
        for agent in receivers:
            assert agent.text == ''
            assert agent.text != message_text

        await sender.send(message)
        for agent in receivers:
            assert agent.text == message_text

    @pytest.mark.asyncio
    async def test_open_conversation(self, ap):
        """Test the conversation functionality
        """

        class SecretKeeper(Agent):
            def __init__(self, *args, **kwargs):
                super(SecretKeeper, self).__init__(*args, **kwargs)
                self.my_secret = 'the earth is flat'

            async def custom_contents_cb(self, message):
                assert message.content.string == 'test'
                reply_content = StringContent(self.my_secret)
                asyncio.ensure_future(self.send_reply(reply_content, message))

        timeout = 1
        requester = ap.create_agent(Agent)
        replier = ap.create_agent(SecretKeeper)

        msg = Message(sender=requester.aid, content=StringContent('test'), recipient=replier.aid)

        reply_fut = requester.open_conversation(msg, timeout)
        assert type(requester) is Agent
        assert type(replier) is SecretKeeper
        reply = await reply_fut
        assert reply[0].content.string == 'the earth is flat'

    @pytest.mark.asyncio
    async def test_get_reply(self, ap):
        """Test the conversation functionality
        """

        class SecretKeeper(Agent):
            def __init__(self, *args, **kwargs):
                super(SecretKeeper, self).__init__(*args, **kwargs)
                self.my_secret = 'the earth is flat'

            async def custom_contents_cb(self, message):
                assert message.content.string == 'test'
                reply_content = StringContent(self.my_secret)
                asyncio.ensure_future(self.send_reply(reply_content, message))

        requester = ap.create_agent(Agent)
        replier = ap.create_agent(SecretKeeper)

        request = Message(sender=requester.aid, content=StringContent('test'), recipient=replier.aid)

        reply_payload = await requester.get_reply(request)
        assert type(requester) is Agent
        assert type(replier) is SecretKeeper
        assert reply_payload.content.string == replier.my_secret

    @pytest.mark.asyncio
    async def test_broadcast_conversation(self, ap):
        """Test if an agent call call an others agent method
        """

        class Receiver(Agent):
            def __init__(self, *args, **kwargs):
                super(Receiver, self).__init__(*args, **kwargs)
                self.text = ''

            async def custom_contents_cb(self, message):
                assert message.content.string == request_text
                self.text = message.content.string

        class SecretKeeper(Agent):
            def __init__(self, *args, **kwargs):
                super(SecretKeeper, self).__init__(*args, **kwargs)
                self.my_secret = 'the earth is flat and my platform_name is {}'.format(self.aid)

            async def custom_contents_cb(self, message):
                assert message.content.string == request_text
                reply_content = StringContent(self.my_secret)
                asyncio.ensure_future(self.send_reply(reply_content, message))

        requester = ap.create_agent(Agent)
        replier = ap.create_agent(SecretKeeper)
        receivers = [ap.create_agent(Receiver) for i in range(5)]

        request_text = "send this from agent 1 to all others"
        request = Message(sender=requester.aid, content=StringContent(request_text),
                          recipient=None, routing='broadcast')

        for agent in receivers:
            assert agent.text == ''
            assert agent.text != request_text

        replies = await requester.get_reply(request, 1)
        assert type(requester) is Agent
        assert type(replier) is SecretKeeper
        assert type(receivers[0]) is Receiver

        assert len(replies) == 1
        assert replies[0].content.string == replier.my_secret

        for agent in receivers:
            assert agent.text == request_text

    @pytest.mark.asyncio
    async def test_dummy_connector(self, event_loop):
        """Test the dummy interface
        """

        class SecretKeeper(Agent):
            def __init__(self, *args, **kwargs):
                super(SecretKeeper, self).__init__(*args, **kwargs)
                self.my_secret = 'the earth is flat'

            @provide
            def get_secret(self):
                return self.my_secret

        timeout = 1
        platform1 = AgentPlatform(platform_name='foo1', loop=event_loop)
        platform2 = AgentPlatform(platform_name='foo2', loop=event_loop)
        with pytest.raises(KeyError):
            AgentPlatform(platform_name='foo2', loop=event_loop)

        requester = platform1.create_agent(Agent)
        replier = platform2.create_agent(SecretKeeper)

        reply = await requester.remote_process_call('get_secret', timeout=timeout, recipient=replier.aid)
        assert type(requester) is Agent
        assert type(replier) is SecretKeeper
        assert reply == 'the earth is flat'
        platform1.stop()
        platform2.stop()

    @pytest.mark.asyncio
    async def test_dummy_broadcast(self, event_loop):
        """Test broadcast conversations with the dummy interface
        """

        class Receiver(Agent):
            def __init__(self, *args, **kwargs):
                super(Receiver, self).__init__(*args, **kwargs)
                self.text = ''

            async def receive(self, message):
                self.text = message.content.function

        class SecretKeeper(Agent):
            def __init__(self, *args, **kwargs):
                super(SecretKeeper, self).__init__(*args, **kwargs)
                self.my_secret = 'the earth is flat and my aid is {}'.format(self.aid)

            @provide
            def get_secret(self):
                return self.my_secret

        platform1 = AgentPlatform('foo1', event_loop)
        platform2 = AgentPlatform('foo2', event_loop)

        requester = platform1.create_agent(Agent)
        replier1 = platform2.create_agent(SecretKeeper)
        replier2 = platform2.create_agent(SecretKeeper)
        receivers1 = [platform1.create_agent(Receiver) for _ in range(5)]
        receivers2 = [platform2.create_agent(Receiver) for _ in range(5)]

        for agent in receivers1:
            assert agent.text == ''

        for agent in receivers2:
            assert agent.text == ''

        assert type(requester) is Agent
        assert type(replier1) is SecretKeeper
        assert type(replier2) is SecretKeeper
        assert type(receivers1[0]) is Receiver
        assert type(receivers2[0]) is Receiver

        secrets = await requester.remote_process_call('get_secret', timeout=1, routing='broadcast')
        assert 'the earth is flat and my aid is {}'.format(replier1.aid) in secrets
        assert 'the earth is flat and my aid is {}'.format(replier2.aid) in secrets

        for agent in receivers1:
            assert agent.text == 'get_secret'

        for agent in receivers2:
            assert agent.text == 'get_secret'

        platform1.stop()
        platform2.stop()

    def test_parse_aid(self):
        address_1 = 'foo/32'
        m_addr, aid = MessageTransportSystem.parse_aid(address_1)
        assert m_addr == 'foo'
        assert aid == '32'

        address_2 = 'foo'
        m_addr, aid = MessageTransportSystem.parse_aid(address_2)
        assert m_addr == 'foo'
        assert aid == ''

        address_3 = '/3'
        with pytest.raises(ValueError) as exc:
            MessageTransportSystem.parse_aid(address_3)
        assert exc.match('No platform name specified')

        # TODO: Move this to agent_platform init test
        # address_4 = 'ungültig/3'
        # with pytest.raises(ValueError) as exc:
        #     MessageTransportSystem.parse_aid(address_4)
        # assert exc.match('are allowed as platform name.')

        # address_5 = 'foo//3'
        # with pytest.raises(ValueError) as exc:
        #     MessageTransportSystem.parse_aid(address_5)
        # assert exc.match('are allowed as agent name.')

        # address_6 = 'foo/ungültig'
        # with pytest.raises(ValueError) as exc:
        #     MessageTransportSystem.parse_aid(address_6)
        # assert exc.match('are allowed as agent name.')


@pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
class TestZigBee:
    @pytest.mark.asyncio
    async def test_update_task(self, platform_name, event_loop):
        ap = AgentPlatform(platform_name, event_loop, update_interval=0.1)
        mts = ap._message_transport
        log.debug("{} Started...".format(mts))
        mts.start()
        await asyncio.sleep(1)
        mts.stop()
        assert mts.other_platforms == ['remote_platform']
        mts.stop()


@pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
class TestRemote:
    @pytest.mark.asyncio
    async def test_update_platform_register(self, event_loop):
        ap = AgentPlatform('remote_platform', event_loop, update_interval=0.1)
        mts = ap._message_transport
        log.debug("{} Listening...".format(mts))
        try:
            await asyncio.sleep(1000)
        except KeyboardInterrupt:
            mts.stop()
