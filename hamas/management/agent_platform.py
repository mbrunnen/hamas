# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    30.11.2016
#   LICENSE:    MIT
#   FILE:       agent_platform.py
# =============================================================================

import itertools
import logging
import string

from hamas.transport.message_transport import MessageTransportSystem
from .agents import Agent

log = logging.getLogger(__name__)


class AgentPlatform(object):
    _allowed_chars = '_' + string.ascii_letters + string.digits

    def __init__(self, machine_name, loop, update_interval=60, regex='/dev/ttyUSB'):
        def generate_name():
            gen_new = itertools.count()
            while True:
                for i in self._free_names:
                    self._free_names.remove(i)
                    yield i
                yield next(gen_new)

        assert set(machine_name) <= set(self._allowed_chars), "Only {} characters are allowed as machine_name.".format(
            self._allowed_chars)
        self._loop = loop
        self._machine_name = machine_name
        self._message_transport = MessageTransportSystem(platform=self, update_interval=update_interval, regex=regex)
        self.__agents = dict()
        self._last_num = 0
        self._free_names = list()
        self._name_gen = generate_name()

    async def start(self):
        await self._message_transport.start()

    def stop(self):
        self._message_transport.stop()

    @property
    def machine_name(self):
        return self._machine_name

    @property
    def loop(self):
        return self._loop

    @property
    def agents(self):
        return self.__agents

    def create_agent(self, agent_class, *args, **kwargs):
        """Create an agent

        Args:
            agent_class (class): Passes the class of the required Agent
            args (list): Passes the arguments to the constructor of the agent
                class
            kwargs (dict): Passes the keyword arguments to the constructor of
                the agent class
        """
        assert issubclass(agent_class, Agent)
        agent_name = str(next(self._name_gen))
        aid = self._machine_name + '/' + agent_name
        agent = agent_class(*args, aid=aid, mts=self._message_transport, **kwargs)
        self.__agents[aid] = agent
        log.info("Platform created agent {}.".format(agent))
        self._last_num += 1
        return agent

    def destroy_agent(self, aid):
        _, num = self._message_transport.parse_aid(aid)
        self._free_names.append(int(num))
        del self.__agents[aid]
        log.info("Platform destroyed agent {}.".format(aid))
