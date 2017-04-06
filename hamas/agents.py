# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    14.07.2016
#   LICENSE:    MIT
#   FILE:	agents.py
# =============================================================================
"""The agent module implements the base :class:`Agent` class. All agents should be derived from this class. The agents
can have special methods, which can be called by other agents and are decorated with :func:`provide`. To handle their
conversations they have with other agents they use the :class:`ConversationRegister`.
"""

import asyncio
import collections
import logging
import string
import time

from .exceptions import TransmissionError, AgentError
from .transport.contents import RemoteProcessCall, RemoteProcessReply, \
    StringContent
from .transport.messages import Message

log = logging.getLogger(__name__)


class ConversationRegister(object):
    """A dictionary for storing the conversations. When a new conversation is created, by calling
    :meth:`new_conversation`, a new :class:`asyncio.Queue` is created and a :class:`asyncio.Future` is returned.
    Every message has a conversation identifier, so the agent can group all messages with the same conversation ID in
    this register. The agent can :meth:`put` new messages in this register, but it can also :meth:`get` a message when
    it has time to process a message. When the agent considers a conversation as finished, it can set a result for this
    conversation in the corresponding `future`.

    Attributes:
        _queues(dict): A dictionary with the conversation ID `conv_id` as key and a :class:`asyncio.Queue` as value.
        _futs(dict): A dictionary with the conversation ID `conv_id` as key and a :class:`asyncio.Future` as value.
    """

    def __init__(self):
        self._queues = collections.defaultdict(asyncio.Queue)
        self._futs = collections.defaultdict(asyncio.Future)

    def __len__(self):
        """`len(self)` returns the quantity of unfinished conversations.
        """
        return len(self._queues)

    def __contains__(self, conv_id):
        """`conv_id in self` returns `True` or `False`, whether `conv_id` is an active conversation or not.
        """
        return conv_id in self._queues

    def new_conversation(self, conv_id):
        """Allocate a new conversation including a :class:`asyncio.Queue` and a :class:`asyncio.Future`.

        Arguments:
            conv_id(bytes): The key which allows access to the conversation.
        """
        log.debug(
            "Started a new Queue with ID {}. There are now {:d} queues in this register.".
            format(conv_id, len(self._queues) + 1))
        assert conv_id not in self
        fut = asyncio.Future()
        self._futs[conv_id] = fut
        queue = asyncio.Queue()
        self._queues[conv_id] = queue
        if len(self._queues) > 100:
            log.warning("The list of queues is getting long: {:d}".format(
                len(self._queues)))
        return fut

    async def put(self, conv_id, msg):
        """Put a new message in the register.

        Arguments:
            conv_id(bytes): The key which allows access to the conversation.
            msg(Message): The incoming message associated with this conversation.
        """
        assert conv_id in self
        await self._queues[conv_id].put(msg)

    async def get(self, conv_id):
        """Remove and return an item from the queue. If queue is empty, wait until an item is available.

        Arguments:
            conv_id(bytes): The key which allows access to the conversation.
        Returns:
            msg(Message): The incoming message associated with this conversation.
        """
        assert conv_id in self
        return await self._queues[conv_id].get()

    def set_result(self, conv_id, result):
        log.debug('Finished queue {}.'.format(conv_id))
        # the queue is now considered finished
        self._queues.pop(conv_id)
        fut = self._futs.pop(conv_id)
        # in the case there are more than one consumer
        fut.set_result(result)


def provide(func):
    """:func:`provide` acts as function decorator and is used for methods, that the agent provides as a service to other
    agents.
    """

    func.provided = True
    return func


class Agent(object):
    """The base class for all other agents. An instance is already able to communicate to other instances. In
    particular, it uses a :class:`ConversationRegister` and a :class:`MessageTransportSystem` for the connunication with
    other agents.

    Args:
        aid(str): The agent's unique identifier.
        mts(MessageTransportSystem): The :class:`MessageTransportSystem` used by this agent.
    """

    _allowed_chars = '/_' + string.ascii_letters + string.digits

    def __init__(self, mts, aid):
        assert set(aid) <= set(
            self._allowed_chars), "{} is not allowed as AID.".format(aid)
        self._aid = aid
        self._mts = mts
        # TODO: pass the loop as argument
        self._loop = mts.loop
        self._conversations = ConversationRegister()
        # TODO: add timeout attribute

    @property
    def aid(self):
        """str: The unique agent identifier. Composed of the platform name and an agent name.
        """
        return self._aid

    @property
    def am_aid(self):
        """str: The agent identifier of the :class:`AgentManager`.
        """
        return self._mts.platform_name + '/0'

    @property
    def platform_name(self):
        """str: The first part of the agent's indentifier, the platform name
        """
        return self._mts.platform_name

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
            reply_fut = self._conversations.new_conversation(conv_id)
            asyncio.ensure_future(self._message_handler(conv_id, timeout, 1))
        elif message.routing == 'broadcast':
            reply_fut = self._conversations.new_conversation(conv_id)
            asyncio.ensure_future(
                self._message_handler(conv_id, timeout, None))
        else:
            raise TransmissionError(
                'Unknown routing {}.'.format(message.routing))
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

    async def remote_process_call(self,
                                  function,
                                  *args,
                                  recipient=None,
                                  timeout=5,
                                  routing='unicast',
                                  **kwargs):
        # TODO: rename to request
        call = RemoteProcessCall(function, args, kwargs)
        message = Message(
            performative='request',
            sender=self._aid,
            recipient=recipient,
            content=call,
            routing=routing, )
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
                log.error('Got a unexpected performative: {}'.format(
                    reply.performative))
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
                    log.error('Got a unexpected performative: {}'.format(
                        r.performative))
            return return_values

    async def receive(self, message):
        if message.conversation_id in self._conversations:
            # This agent started the conversation
            await self._conversations.put(message.conversation_id, message)
        elif message.performative == 'request':
            await self._on_request_cb(message)
        elif message.performative is None:
            # old message types
            await self.custom_contents_cb(message)
        else:
            log.warning("Got an unexpected reply. Perhaps timed out.\n\t{}".
                        format(message.content))

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
                msg = await asyncio.wait_for(
                    self._conversations.get(conv_id), timeout)
            except asyncio.TimeoutError:
                timeout_reached = True
            else:
                log.debug('Message queue {} got a new message:\n\t{}'.format(
                    conv_id, msg))
                messages.append(msg)
            finally:
                end = time.monotonic()
                log.debug('Queue {} waited {:.3f}s for new message'.format(
                    conv_id, end - start))
        self._conversations.set_result(conv_id, messages)

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
                    content = StringContent("Agent {} failed on function {}.".
                                            format(self.aid, function))
            else:
                performative = 'refuse'
                content = StringContent("Agent {} don't provide function {}.".
                                        format(self.aid, function))
        else:
            performative = 'refuse'
            content = StringContent(
                "Agent {} don't has function {}.".format(self.aid, function))
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
        log.debug(
            "No 'custom_contents_cb' callback for agent '{}' provided. Message dropped:\n\t{}".
            format(self, message))
