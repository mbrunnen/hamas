# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    07.10.2016
#   LICENSE:    MIT
#   FILE:	    contents.py
# =============================================================================
"""Class for the payload in the messages.

This class represent the application layer of the agent communication protocol.
Whereas the message class can be seen as the envelope, this class can be seen as
the letter inside the envelope. The payload is not important for the delivery
of the message, but is used by the receiving Agent itself.
"""

from hamas.transport.serializable import Serializable


class Content(Serializable):
    pass


class RemoteProcess(Content):
    def __init__(self, function):
        """

        Args:
            function (str):
        """
        self._function = function

    @property
    def function(self):
        return self._function

    def _get_init_args(self):
        return (self._function,)

    def __eq__(self, other):
        return self._function == other.function


class RemoteProcessCall(RemoteProcess):
    _code = b'\x01'

    def __init__(self, function, args, kwargs):
        """

        Args:
            function (str):
            args (tuple):
            kwargs (dict):
        """
        super(RemoteProcessCall, self).__init__(function)
        self._args = args
        self._kwargs = kwargs

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs

    def _get_init_args(self):
        super_args = super(RemoteProcessCall, self)._get_init_args()
        return super_args + (self.args, self.kwargs)

    def __eq__(self, other):
        return super(RemoteProcessCall, self).__eq__(other) and \
               self._args == other.args and \
               self._kwargs == other.kwargs

    def __repr__(self):
        return "Remote function call for '{}' with the arguments {} and {}.".format(self.function,
                                                                                    self.args,
                                                                                    self.kwargs)


class RemoteProcessReply(RemoteProcess):
    _code = b'\x02'

    def __init__(self, function, returns):
        """

        Args:
            function (str):
            returns (str, float, int, list, dict):
        """
        super(RemoteProcessReply, self).__init__(function)
        self._returns = returns

    @property
    def returns(self):
        return self._returns

    def _get_init_args(self):
        super_args = super(RemoteProcessReply, self)._get_init_args()
        return super_args + (self._returns,)

    def __eq__(self, other):
        return super(RemoteProcessReply, self).__eq__(other) and \
               self._returns == other.returns

    def __repr__(self):
        return "Remote function reply for '{}' returned {}.".format(self.function, self.returns)


class StringContent(Content):
    _code = b'\x03'

    def __init__(self, string):
        assert type(string) is str
        self.string = string

    def __eq__(self, other):
        return super(StringContent) and \
               self.string == other.string

    def __repr__(self):
        return self.string

    def _get_init_args(self):
        return (self.string,)


class DictionaryContent(Content):
    _code = b'\x04'

    def __init__(self, dictionary):
        assert type(dictionary) is dict
        self.dictionary = dictionary

    def _get_init_args(self):
        return (self.dictionary,)

    def __eq__(self, other):
        return self.dictionary == other.dictionary
