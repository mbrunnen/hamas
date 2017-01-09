# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    14.10.2016
#   LICENSE:    MIT
#   FILE:       test_contents.py
# =============================================================================
"""Tests for the Content class
"""

import itertools
import logging

import pytest

from hamas import DictionaryContent, StringContent
from hamas.transport import RemoteProcessCall, RemoteProcessReply

log = logging.getLogger(__name__)

log.setLevel(logging.DEBUG)


class TestRemoteProcessCall:
    """Test case for the content.
    """

    def test_equality(self):
        args = [a for a in itertools.product(['function_name', 'different_function'],
                                             [(), ('one string',), (2,), (-3.141,), ('mulitple args', 42, 2.3), ],
                                             [{}, {'string': 'str'}, {'int': 1}, {'float': -2.5}, {'list': [4, 2]},
                                              {'dict': {'a': 'b', 0: 2.0}},
                                              {'string': 'str', 'float': -2.5, 'int': 1, 'list': [4, 2],
                                               'dict': {'a': 'b', 0: 2.0}}])]
        for args1, args2 in itertools.product(args, args):
            rpc1 = RemoteProcessCall(*args1)
            rpc2 = RemoteProcessCall(*args2)
            if args1 == args2:
                assert rpc1 == rpc2
                assert rpc2 == rpc1
            else:
                assert rpc1 != rpc2
                assert rpc2 != rpc1

    @pytest.mark.parametrize('args, kwargs',
                             itertools.product([
                                 (),
                                 ('one string',),
                                 (2,),
                                 (-3.141,),
                                 ('mulitple args', 42, 2.3),
                             ], [
                                 {},
                                 {'string': 'str'},
                                 {'int': 1},
                                 {'float': -2.5},
                                 {'list': [4, 2]},
                                 {'dict': {'a': 'b', 0: 2.0}},
                                 {'string': 'str', 'float': -2.5, 'int': 1, 'list': [4, 2], 'dict': {'a': 'b', 0: 2.0}}
                             ]))
    def test_serialization(self, args, kwargs):
        """Test the serialization of Content.
        """
        content = RemoteProcessCall('function', args, kwargs)
        serialized = content.serialize()
        assert type(serialized) is bytes
        deserialized = content.deserialize(serialized)
        assert content == deserialized
        log.info("Length of the serialized {} is {:d}".format(content.__class__.__name__, len(serialized)))
        pickled = content.pickle()
        unpickled = content.unpickle(pickled)
        assert content == unpickled
        log.info("Length of the pickled {} is {:d}".format(content.__class__.__name__, len(pickled)))
        log.info("Difference: Pickled - Serialized = {:d}".format(len(pickled) - len(serialized)))
        log.info("Ratio: Serialiazed/Pickled * 100% = {:.2%}".format(len(serialized) / len(pickled)))


class TestRemoteProcessReply:
    def test_equality(self):
        args = [a for a in itertools.product(['function_name', 'different_function'],
                                             [None, (), ('one string',), (2,), (-3.141,), ('mulitple args', 42, 2.3),
                                              {}, {'string': 'str'}, {'int': 1}, {'float': -2.5}, {'list': [4, 2]},
                                              {'dict': {'a': 'b', 0: 2.0}},
                                              {'string': 'str', 'float': -2.5, 'int': 1, 'list': [4, 2],
                                               'dict': {'a': 'b', 0: 2.0}}])]
        for args1, args2 in itertools.product(args, args):
            rpr1 = RemoteProcessReply(*args1)
            rpr2 = RemoteProcessReply(*args2)
            if args1 == args2:
                assert rpr1 == rpr2
                assert rpr2 == rpr1
            else:
                try:
                    assert rpr1 != rpr2
                    assert rpr2 != rpr1
                except AssertionError as exc:
                    log.error("Comparison between {} and {} went wrong.".format(rpr1, rpr2))
                    raise exc

    @pytest.mark.parametrize('returns', [
        'string', 2, -3.141,
        (),
        ('a tuple', 2.0),
        [],
        ['a list', 42, 2.3],
        {},
        {'dict': {'a': 'b', 0: 2.0}},
    ])
    def test_serialization(self, returns):
        """Test the serialization of Content.
        """
        content = RemoteProcessReply('function', returns)
        serialized = content.serialize()
        assert type(serialized) is bytes
        deserialized = content.deserialize(serialized)
        assert content == deserialized
        log.info("Length of the serialized {} is {:d}".format(content.__class__.__name__, len(serialized)))
        pickled = content.pickle()
        unpickled = content.unpickle(pickled)
        assert content == unpickled
        log.info("Length of the pickled {} is {:d}".format(content.__class__.__name__, len(pickled)))
        log.info("Difference: Pickled - Serialized = {:d}".format(len(pickled) - len(serialized)))
        log.info("Ratio: Serialiazed/Pickled * 100% = {:.2%}".format(len(serialized) / len(pickled)))


class TestStringContent:
    def test_equality(self):
        args = ('string', 'other')
        for arg1, arg2 in itertools.product(args, args):
            str1 = StringContent(arg1)
            str2 = StringContent(arg2)
            if arg1 == arg2:
                assert str1 == str2
                assert str2 == str1
            else:
                assert str1 != str2
                assert str2 != str1

    def test_serialization(self):
        """Test the serialization of Content.
        """
        content = StringContent('a string')
        serialized = content.serialize()
        assert type(serialized) is bytes
        deserialized = content.deserialize(serialized)
        assert content == deserialized
        log.info("Length of the serialized {} is {:d}".format(content.__class__.__name__, len(serialized)))
        pickled = content.pickle()
        unpickled = content.unpickle(pickled)
        assert content == unpickled
        log.info("Length of the pickled {} is {:d}".format(content.__class__.__name__, len(pickled)))
        log.info("Difference: Pickled - Serialized = {:d}".format(len(pickled) - len(serialized)))
        log.info("Ratio: Serialiazed/Pickled * 100% = {:.2%}".format(len(serialized) / len(pickled)))


class TestDictionaryContent:
    def test_equality(self):
        args = ({}, {1: 'b'}, {2: '15'}, {1: 'b', 2: '15'})
        for arg1, arg2 in itertools.product(args, args):
            dict1 = DictionaryContent(arg1)
            dict2 = DictionaryContent(arg2)
            if arg1 == arg2:
                assert dict1 == dict2
                assert dict2 == dict1
            else:
                assert dict1 != dict2
                assert dict2 != dict1

    def test_serialization(self):
        """Test the serialization of Content.
        """
        content = DictionaryContent(
            {'string': 'str', 'float': -2.5, 'int': 1, 'list': [4, 2], 'dict': {'a': 'b', 0: 2.0}})
        serialized = content.serialize()
        assert type(serialized) is bytes
        deserialized = content.deserialize(serialized)
        assert content == deserialized
        log.info("Length of the serialized {} is {:d}".format(content.__class__.__name__, len(serialized)))
        pickled = content.pickle()
        unpickled = content.unpickle(pickled)
        assert content == unpickled
        log.info("Length of the pickled {} is {:d}".format(content.__class__.__name__, len(pickled)))
        log.info("Difference: Pickled - Serialized = {:d}".format(len(pickled) - len(serialized)))
        log.info("Ratio: Serialiazed/Pickled * 100% = {:.2%}".format(len(serialized) / len(pickled)))
