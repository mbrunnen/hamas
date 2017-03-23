# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    30.11.2016
#   LICENSE:    MIT
#   FILE:       management.py
# =============================================================================
"""
"""

import itertools
import logging
import string

from hamas.agents import Agent, provide
from hamas.transport.message_transport import MessageTransportSystem

log = logging.getLogger(__name__)


class AgentPlatform(object):
    _allowed_chars = '_' + string.ascii_letters + string.digits

    def __init__(self, machine_name, loop, update_interval=60,
                 regex='/dev/ttyUSB'):
        def generate_name():
            gen_new = itertools.count()
            while True:
                for i in self._free_names:
                    self._free_names.remove(i)
                    yield i
                yield next(gen_new)

        assert set(machine_name) <= set(
            self._allowed_chars), "Only {} characters are allowed as machine_name.".format(
            self._allowed_chars)
        self._loop = loop
        self._machine_name = machine_name
        self._message_transport = MessageTransportSystem(platform=self,
                                                         update_interval=update_interval,
                                                         regex=regex)
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
        agent = agent_class(*args, aid=aid, mts=self._message_transport,
                            **kwargs)
        self.__agents[aid] = agent
        log.info("Platform created agent {}.".format(agent))
        self._last_num += 1
        return agent

    def destroy_agent(self, aid):
        _, num = self._message_transport.parse_aid(aid)
        self._free_names.append(int(num))
        del self.__agents[aid]
        log.info("Platform destroyed agent {}.".format(aid))


class AgentManager(Agent):
    """First Agent running which creates, runs and manages the agents.

    Attributes:
        _white_pages (dict): Dictionary which contains the agent description, actually the class name.
        _platform (AgentPlatform):

    """
    __in_create = False

    @classmethod
    def create(cls, machine_name, loop, regex='/dev/ttyUSB'):
        """Factory function which instantiates a AgentManager agent.

        Do not instantiate the AgentManager directly. It is a special
        agent, which has no ID given, so it will create it's own ID.
        Also it will create a MessageTransportSystem.

        Arguments:
            machine_name(str):The management ID must be given. It can read from
                a config file.
            loop (BaseEventLoop): The event loop.
            regex(str): The regular expression to find the serial port.
        Returns:
            AgentManager
        """
        platform = AgentPlatform(machine_name=machine_name, loop=loop,
                                 regex=regex)
        manager = platform.create_agent(AgentManager, platform=platform)
        return manager

    def __init__(self, platform, *args, **kwargs):
        """Initialise the AgentManager
        """
        assert type(
            platform) is AgentPlatform, "Create the {} with its create method.".format(
            self.__class__.__name__)
        super(AgentManager, self).__init__(*args, **kwargs)
        self._platform = platform
        self._white_pages = dict()
        self._register(self)

    @property
    def other_machines(self):
        return self._mts.other_machines

    async def start(self):
        await self._platform.start()

    def stop(self):
        """ Cancel the coroutines of the AgentManager.

        """
        self._platform.stop()

    async def wait_for_zigbee(self):
        await self._mts.wait_for_zigbee()

    @property
    def white_pages(self):
        return self._white_pages

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
        agent = self._platform.create_agent(agent_class, *args, **kwargs)
        self._register(agent)
        return agent

    def destroy_agent(self, aid):
        self._deregister(aid)
        self._platform.destroy_agent(aid)

    def _register(self, agent):
        log.info("AgentManager registered {}.".format(agent))
        self._white_pages[agent.aid] = agent.__class__.__name__

    def _deregister(self, aid):
        log.info("AgentManager deregistered {}.".format(aid))
        del self._white_pages[aid]

    @provide
    def perform_create_agent(self, agent_class_name):
        # TODO : args, kwargs

        path, class_name = agent_class_name.rsplit('.', 1)
        module = importlib.import_module(path)
        agent_class = getattr(module, class_name)
        assert issubclass(agent_class, Agent)
        agent = self.create_agent(agent_class)
        return agent.aid

    @provide
    def perform_destroy_agent(self, aid):
        self.destroy_agent(aid)
        return aid

    @provide
    def get_agents(self, agent_class_names=None):
        addresses = {}
        if agent_class_names is None:
            agent_class_names = list(set(self._white_pages.values()))
        if not type(agent_class_names) is list:
            agent_class_names = [agent_class_names]
        for class_name in agent_class_names:
            aids = list()
            for aid, desc in self._white_pages.items():
                if desc == class_name:
                    aids.append(aid)
            addresses[class_name] = aids
        return addresses
