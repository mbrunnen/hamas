# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    14.07.2016
#   LICENSE:    MIT
#   FILE:	agents.py
# =============================================================================
"""Agent Base Class

All Agent should be derived from this class.
"""

import asyncio
import logging
import string
import time

from hamas.transport.contents import RemoteProcessCall, RemoteProcessReply, StringContent
from hamas.transport.messages import Message
from .queue_register import QueueRegister
from ..exceptions import TransmissionError, AgentError

log = logging.getLogger(__name__)


def provide(func):
    func.provided = True
    return func


class Agent(object):
    """Agent Base Class

    Attributes:
        _aid(str): unique agent identifier
        _mts: The machine, necessary to talk to other agents
        _loop (BaseEventLoop): The loop which runs this agent
        _queues (QueueRegister): A register for the conversation control.
    """

    _allowed_chars = '/_' + string.ascii_letters + string.digits

    def __init__(self, mts, aid):
        """Initialise an agent

        Args:
            aid(str): unique agent URL
            mts(MessageTransportSystem): TODO
        """

        assert set(aid) <= set(self._allowed_chars), "{} is not allowed as AID.".format(aid)
        self._aid = aid
        self._mts = mts
        # TODO: pass the loop as argument
        self._loop = mts.loop
        self._queues = QueueRegister()
        # TODO: add timeout attribute

    @property
    def aid(self):
        return self._aid

    @property
    def am_aid(self):
        return self._mts.machine_name + '/0'

    @property
    def machine_name(self):
        return self._mts.machine_name

    @provide
    def get_aid(self):
        return self._aid

    def __repr__(self):
        return '{} ({})'.format(self.__class__.__name__, self.aid)

    def open_conversation(self, message, timeout=5):
        """This method transmits a request and returns a reply future.

        It creates a Future with the reply of the addressed agent. When the
        addressed agent replies, the future's result will be set. If the
        timeout is reached before any reply, an timeout exception will be
        thrown If the request is sent as broadcast, the communication will
        set the result with the received replies before the timeout after a
        certain timeout. This is a coroutine because it has to wait for send
        to finish.

        Args:
            message (Message): The conversation opener, i.e. a remote process call
            timeout (float): After this amount of time the conversation times out


        Returns:
            reply (Future): The reply future contains the reply of the the call
        """
        conv_id = message.conversation_id
        if message.routing == 'unicast':
            reply_fut = self._queues.new_queue(conv_id, self._message_handler(conv_id, timeout, 1))
        elif message.routing == 'broadcast':
            reply_fut = self._queues.new_queue(conv_id, self._message_handler(conv_id, timeout, None))
        else:
            raise TransmissionError('Unknown routing {}.'.format(message.routing))
        asyncio.ensure_future(self.send(message))
        return reply_fut

    async def get_reply(self, message, timeout=5):
        """Opens a conversation and returns directly the reply

        Sometimes it is more useful to get the reply instead of the future.

        Args:
            message (Message): The request message to open the conversation.
            timeout (float): The amount of time the requesting agent is willing to wait

        Returns:
            reply (Reply,list):

        """
        reply = await self.open_conversation(message, timeout)
        if len(reply) == 1 and message.routing == 'unicast':
            return reply[0]
        else:
            return reply

    async def send(self, message):
        """Send a message from this agent to another

        Args:
            message (Message): The message for the recipient
        """
        if message.routing != 'broadcast':
            assert message.recipient, "No recipient provided."
        assert type(message) is Message
        await self._mts.receive(message)

    async def remote_process_call(self, function, *args, recipient=None, timeout=5, routing='unicast', **kwargs):
        # TODO: rename to request
        call = RemoteProcessCall(function, args, kwargs)
        message = Message(
            performative='request',
            sender=self._aid,
            recipient=recipient,
            content=call,
            routing=routing,
        )
        reply = await self.get_reply(message, timeout)
        if not reply:
            raise AgentError("No replies.")
        if routing == 'unicast':
            if reply.performative == 'failure' or reply.performative == 'refuse':
                log.error(reply.content.string)
                return reply.content.string
            elif reply.performative == 'inform':
                assert reply.content.function == function
                return reply.content.returns
            else:
                log.error('Got a unexpected performative: {}'.format(reply.performative))
        else:
            return_values = []
            for r in reply:
                if r.performative == 'failure' or r.performative == 'refuse':
                    log.error(r.content.string)
                    return_values.append(r.content.string)
                elif r.performative == 'inform':
                    assert r.content.function == function
                    return_values.append(r.content.returns)
                else:
                    log.error('Got a unexpected performative: {}'.format(r.performative))
            return return_values

    async def receive(self, message):
        if message.conversation_id in self._queues:
            # This agent started the conversation
            await self._queues.put(message.conversation_id, message)
        elif message.performative == 'request':
            await self._on_request_cb(message)
        elif message.performative is None:
            # old message types
            await self.custom_contents_cb(message)
        else:
            log.warning("Got an unexpected reply. Perhaps timed out.\n\t{}".format(message.content))

    async def _message_handler(self, conv_id, timeout, num_items):
        def stop_condition():
            if timeout_reached:
                log.debug('Timeout for queue {} reached.'.format(conv_id))
                return True
            if len(messages) == num_items:
                log.debug('List full for queue {}.'.format(conv_id))
                return True
            return False

        messages = []
        timeout_reached = False
        while not stop_condition():
            try:
                start = time.monotonic()
                item = await asyncio.wait_for(self._queues.get(conv_id), timeout)
            except asyncio.TimeoutError:
                timeout_reached = True
            else:
                log.debug('Message queue {} got a new item:\n\t{}'.format(conv_id, item))
                self._queues.task_done(conv_id)
                messages.append(item)
            finally:
                end = time.monotonic()
                log.debug('Queue {} waited {:.3f}s for new item'.format(conv_id, end - start))
        self._queues.set_result(conv_id, messages)

    async def _on_request_cb(self, message):
        function = message.content.function
        args = message.content.args
        kwargs = message.content.kwargs
        if hasattr(self, function):
            func = getattr(self, function)
            if hasattr(func, 'provided'):
                try:
                    performative = 'inform'
                    returns = func(*args, **kwargs)
                    content = RemoteProcessReply(function, returns)
                except Exception as exc:
                    log.exception(exc)
                    performative = 'failure'
                    content = StringContent("Agent {} failed on function {}.".format(self.aid, function))
            else:
                performative = 'refuse'
                content = StringContent("Agent {} don't provide function {}.".format(self.aid, function))
        else:
            performative = 'refuse'
            content = StringContent("Agent {} don't has function {}.".format(self.aid, function))
        await self.send_reply(content, message, performative)

    async def send_reply(self, content, message, performative=None):
        reply = Message(
            performative=performative,
            sender=self._aid,
            content=content,
            recipient=message.sender,
            routing='unicast',
            conversation_id=message.conversation_id)

        await self.send(reply)

    async def custom_contents_cb(self, message):
        """Normally everything should work over RemoteProcessCall.

        If the application uses other payloads than RemoteProcessCalls this function is called.
        This is here make the transition easier.
        Args:
            message(Message): A message with custom content
        """
        log.debug("No 'custom_contents_cb' callback for agent '{}' provided. Message dropped:\n\t{}".format(self, message))
