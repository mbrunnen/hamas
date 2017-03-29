# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    11.08.2016
#   LICENSE:    MIT
#   FILE:       test_agents.py
# =============================================================================

import asyncio
import itertools
import logging
import random
import unittest.mock
import uuid
import pytest
from hamas import Agent, provide, Message
from hamas.agents import QueueRegister
from hamas.transport import RemoteProcessCall, RemoteProcessReply, \
    StringContent

log = logging.getLogger(__name__)


class TestQueueregister:
    @pytest.mark.asyncio
    async def test_new_queue(self):
        async def queue_consumer(q_id):
            result = await queues.get(q_id)
            queues.task_done(q_id)
            queues.set_result(q_id, result)

        qid = 'test'

        queues = QueueRegister()
        assert queues._queues == {}
        assert queues._queue_futs == {}

        assert qid not in queues
        q_fut = queues.new_queue(qid, queue_consumer(qid))
        assert queues._queues != {}
        assert queues._queue_futs == {'test': q_fut}
        assert qid in queues
        await queues.put(qid, 'the result')
        q_result = await q_fut
        assert qid not in queues
        assert queues._queues == {}
        assert queues._queue_futs == {}
        assert q_result == 'the result'


class TestAgent:
    @pytest.mark.asyncio
    async def test_create_task(self, mts):
        class MyAgent(Agent):
            def __init__(self, n_jobs, *args, **kwargs):
                super(MyAgent, self).__init__(*args, **kwargs)
                self.results = []
                self.jobs = [
                    asyncio.ensure_future(self.my_coro(i))
                    for i in range(n_jobs)
                ]

            async def my_coro(self, x):
                await asyncio.sleep(random.random() / 10)
                self.results.append(x * x)

            async def run(self):
                await asyncio.wait(self.jobs)

        num_jobs = 5
        agent = MyAgent(n_jobs=num_jobs, aid='foo', mts=mts)

        assert len(agent.jobs) == num_jobs
        await agent.run()

        for j in range(num_jobs):
            assert j * j in agent.results

    @pytest.mark.parametrize('args, kwargs',
                             itertools.product([
                                 (),
                                 ('single_arg', ),
                                 ('arg1', 'arg2'),
                             ], [{}, {
                                 'a': 'kwarg1'
                             }, {
                                 'a': 'kwarg1',
                                 'b': 'kwarg2'
                             }]))
    def test_provide_args(self, args, kwargs):
        @provide
        def return_args(self, *fwargs, **fwkwargs):
            return 'self: {}\nargs: {}\nkwarg: {}'.format(
                self, fwargs, fwkwargs)

        assert hasattr(return_args, 'provided')
        assert return_args.provided
        result = return_args('this', *args, **kwargs)
        expected_result = 'self: this\nargs: {}\nkwarg: {}'.format(
            args, kwargs)
        assert expected_result == result

    @pytest.mark.asyncio
    async def test_send(self, mts):
        def make_coroutine(mock):
            async def coroutine(*args, **kwargs):
                return mock(*args, **kwargs)

            return coroutine

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch.object(mts, 'receive', make_coroutine(mock)):
            agent = Agent(
                mts,
                mts.machine_name + '/1', )
            recipient = 'someone'
            msg = Message(
                sender=agent.aid,
                content=StringContent('stuff'),
                recipient=recipient,
                routing='somehow')
            await agent.send(msg)
            mock.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_receive_in_q(self, mts):
        agent = Agent(
            mts,
            mts.machine_name + '/1', )
        sender = 'someone'
        timeout = 1
        conv_id = uuid.uuid4()
        reply_fut = agent._queues.new_queue(conv_id,
                                            agent._message_handler(
                                                conv_id, timeout, 1))
        msg = Message(
            sender=sender,
            content=StringContent('stuff'),
            recipient=agent.aid,
            routing='somehow',
            conversation_id=conv_id)
        await agent.receive(msg)
        reply = await reply_fut
        assert reply[0] == msg

    @pytest.mark.asyncio
    async def test_receive_rp_call_provided(self, mts):
        def make_coroutine(mock):
            async def coroutine(*args, **kwargs):
                return mock(*args, **kwargs)

            return coroutine

        agent = Agent(
            mts,
            mts.machine_name + '/1', )

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch.object(agent, 'send', make_coroutine(mock)):
            sender = 'someone'
            content = RemoteProcessCall('get_aid', (), {})
            msg = Message(
                performative='request',
                sender=sender,
                content=content,
                recipient=agent.aid,
                routing='somehow', )
            await agent.receive(msg)
            reply_msg = Message(
                performative='inform',
                sender=agent.aid,
                content=RemoteProcessReply('get_aid', agent.aid),
                recipient=sender,
                routing='unicast',
                conversation_id=msg.conversation_id)
            mock.assert_called_once_with(reply_msg)

    @pytest.mark.asyncio
    async def test_receive_rp_call_unprovided(self, mts):
        def make_coroutine(mock):
            async def coroutine(*args, **kwargs):
                return mock(*args, **kwargs)

            return coroutine

        agent = Agent(
            mts,
            mts.machine_name + '/1', )

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch.object(agent, 'send', make_coroutine(mock)):
            sender = 'someone'
            function = '_aid'
            content = RemoteProcessCall(function, (), {})
            msg = Message(
                performative='request',
                sender=sender,
                content=content,
                recipient=agent.aid,
                routing='somehow', )
            await agent.receive(msg)
            content = StringContent("Agent {} don't provide function {}.".
                                    format(agent.aid, function))
            reply_msg = Message(
                performative='refuse',
                sender=agent.aid,
                content=content,
                recipient=sender,
                routing='unicast',
                conversation_id=msg.conversation_id)
            mock.assert_called_once_with(reply_msg)

    @pytest.mark.asyncio
    async def test_receive_rp_call_unexistent(self, mts):
        def make_coroutine(mock):
            async def coroutine(*args, **kwargs):
                return mock(*args, **kwargs)

            return coroutine

        agent = Agent(
            mts,
            mts.machine_name + '/1', )

        mock = unittest.mock.MagicMock()
        with unittest.mock.patch.object(agent, 'send', make_coroutine(mock)):
            sender = 'someone'
            function = 'weird_named_function'
            content = RemoteProcessCall(function, (), {})
            msg = Message(
                performative='request',
                sender=sender,
                content=content,
                recipient=agent.aid,
                routing='somehow', )
            await agent.receive(msg)
            content = StringContent(
                "Agent {} don't has function {}.".format(agent.aid, function))
            reply_msg = Message(
                performative='refuse',
                sender=agent.aid,
                content=content,
                recipient=sender,
                routing='unicast',
                conversation_id=msg.conversation_id)
            mock.assert_called_once_with(reply_msg)

    @pytest.mark.asyncio
    async def test_receive_belated_rp_reply(self, mts):
        agent = Agent(
            mts,
            mts.machine_name + '/1', )
        with unittest.mock.patch(
                'hamas.management.agents.log.warning') as mock:
            sender = 'someone'
            content = RemoteProcessReply('get_aid', 'stuff')
            msg = Message(
                performative='inform',
                sender=sender,
                content=content,
                recipient=agent.aid,
                routing='somehow', )
            await agent.receive(msg)
            mock.assert_called_once_with(
                "Got an unexpected reply. Perhaps timed out.\n\tRemote function reply for 'get_aid' returned stuff."
            )

    @pytest.mark.asyncio
    async def test_custom_contents_cb(self, mts):
        def make_coro(mock):
            async def coro(*args, **kwargs):
                mock(*args, **kwargs)

            return coro

        cb_mock = unittest.mock.MagicMock()
        agent = Agent(mts, mts.machine_name + '/1')
        with unittest.mock.patch.object(agent, 'custom_contents_cb',
                                        make_coro(cb_mock)):
            sender = 'someone'
            content = StringContent("stuff")
            msg = Message(
                sender=sender,
                content=content,
                recipient=agent.aid,
                routing='unicast', )
            await agent.receive(msg)
            cb_mock.assert_called_once_with(msg)
