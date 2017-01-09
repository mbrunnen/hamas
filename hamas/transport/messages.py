# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    12.08.2016
#   LICENSE:    MIT
#   FILE:	    messages.py
# =============================================================================
"""The classes that agents can send to each other

A message is mapped to the transport and session layer of the agent
communication protocol. The sender, recipient and routing options are used to
deliver the message. The content field is used by the receiving agent. The
message class is the envelope and the content is the letter. The request class
is necessary to open a session, which is called conversation. A conversation are
all messages with the same conversation ID. The normal use case is that an agent
sends a Request and the receiving agent will answer with an instance of Reply.
The machine will then match these two messages and establish in that
way a conversation.
"""

import importlib
import os
import struct

from hamas.transport.contents import Content
from hamas.transport.serializable import Serializable


class Message(Serializable):
    """The object that agents sends to other agents.

    The sending agent doesn't expect any reply.

    Attributes:
        recipient (str, None): The recipient
        _sender (str): The sender
        content (Content): The content data
        _routing (str): The routing scheme of the message
        __conversation_id (bytes): Control of conversation. This number shall be unique for one conversation. Also this field can only be read.
    """
    _code = b'\x05'

    _performatives = {
        "accept-proposal": '\x01',
        "agree": '\x02',
        "cancel": '\x03',
        "cfp": '\x04',
        "confirm": '\x05',
        "disconfirm": '\x06',
        "failure": '\x07',
        "inform": '\x08',
        "inform-if": '\x09',
        "inform-ref": '\x0A',
        "not-understood": '\x0B',
        "propagate": '\x0C',
        "propose": '\x0D',
        "proxy": '\x0E',
        "query-if": '\x0F',
        "query-ref": '\x10',
        "refuse": '\x11',
        "reject-proposal": '\x12',
        "request": '\x13',
        "request-when": '\x14',
        "request-whenever": '\x15',
        "subscribe": '\x16',
    }

    def __init__(self,
                 sender,
                 content=None,
                 recipient=None,
                 routing='unicast',
                 conversation_id=None,
                 performative=None):
        """Initialise the message

        Arguments:
            performative (str): Type of message.
            sender (str): The sender of the message.
            content (str, dict): The content of the message.
            recipient (str): The recipient.
            routing (str): The routing scheme of the message.
            conversation_id (bytes): ID of the conversation in that the message is exchanged.

        """
        assert performative in self._performatives or performative is None
        self._performative = performative
        assert type(sender) is str
        self._sender = sender
        assert type(content) is bytes or isinstance(content, Content) or content is None
        self.content = content
        assert type(recipient) is str or not recipient
        self._recipient = recipient
        assert type(routing) is str or not routing
        self._routing = routing
        self.__conversation_id = conversation_id if conversation_id else os.urandom(4)

    @property
    def performative(self):
        return self._performative

    @property
    def sender(self):
        """Returns the AID of the sender
        """
        return self._sender

    @property
    def recipient(self):
        return self._recipient

    @property
    def routing(self):
        """Returns the routing scheme of the message.

            Unicast: To one defined recipient.
            Broadcast: To all agents.
        """
        return self._routing

    @property
    def conversation_id(self):
        return self.__conversation_id

    def _get_init_args(self):
        return self._sender, self.content.serialize(), self._recipient, self._routing, self.__conversation_id, self._performative

    @classmethod
    def deserialize(cls, serialized, *args):
        msg = super(Message, cls).deserialize(serialized)
        code, = struct.unpack('c', msg.content[0:1])
        serializer = Serializable.serializers[code]
        path, class_name = serializer.rsplit('.', 1)
        module = importlib.import_module(path)
        serializable = getattr(module, class_name)
        assert issubclass(serializable, Serializable)
        msg.content = serializable.deserialize(msg.content)
        return msg

    def __eq__(self, other):
        return self._performative == other.performative and \
               self._sender == other.sender and \
               self.content == other.content and \
               self._recipient == other.recipient and \
               self._routing == other.routing and \
               self.__conversation_id == other.conversation_id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "Performative: {};Sender: {};Recipient: {};Content: {}".format(self._performative, self._sender, self._recipient, self.content.__class__.__name__)
