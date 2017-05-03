# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    15.08.2016
#   LICENSE:    MIT
#   FILE:	    test_messages.py
# =============================================================================
"""Test the message class
"""

import itertools
import logging
import string
from random import choice

import pytest

from hamas import Message
from hamas import StringContent

log = logging.getLogger(__name__)


def randomstr():
    return ''.join(choice(string.ascii_lowercase) for _ in range(50))


class TestMessage:
    def test_equality(self):
        args = [a for a in itertools.product(
            ['sender', 'other sender'],
            [StringContent('stuff'),
             StringContent('other stuff')],
            [None, 'recipient',
             'other recipient'],
            ['somehow', 'somehow else'],
            [b'an id', b'another id'],
            ['inform', None])]
        for args1, args2 in itertools.product(args, args):
            msg1 = Message(*args1)
            msg2 = Message(*args2)
            if args1 == args2:
                assert msg1 == msg2
                assert msg2 == msg1
            else:
                assert msg1 != msg2
                assert msg2 != msg1

    def test_conversation_id(self):
        sender = 'sender'
        payload = StringContent('stuff')
        recipient = 'recipient'
        routing = 'somehow'
        msg1 = Message(sender, payload, recipient, routing=routing)
        msg2 = Message(sender, payload, recipient, routing=routing)
        assert msg1 != msg2

    @pytest.mark.parametrize(
        'sender, content, recipient, routing, conv_id, performative',
        itertools.product(['sender', 'other sender'],
                          [StringContent('stuff'),
                           StringContent('other stuff')],
                          [None, 'recipient', 'other recipient'],
                          ['somehow', 'somehow else'],
                          [None, b'an id', b'another id'],
                          ['inform', None]))
    def test_serialization(self, sender, content, recipient, routing, conv_id,
                           performative):
        """Test the serialization of Messages.
        """
        message = Message(sender=sender, content=content, recipient=recipient,
                          routing=routing,
                          conversation_id=conv_id, performative=performative)
        serialized = message.serialize()
        assert type(serialized) is bytes
        deserialized = message.deserialize(serialized)
        assert message == deserialized
        print(
            "Length of the serialized Message is {:d}".format(len(serialized)))
        pickled = message.pickle()
        unpickled = message.unpickle(pickled)
        assert message == unpickled
        print("Length of the pickled Message is {:d}".format(len(pickled)))
        print("Difference: Pickled - Serialized = {:d}".format(
            len(pickled) - len(serialized)))
        print("Ratio: Serialiazed/Pickled * 100% = {:.2%}".format(
            len(serialized) / len(pickled)))
