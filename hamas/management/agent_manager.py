# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    17.08.2016
#   LICENSE:    MIT
#   FILE:	agent_manager.py
# =============================================================================
"""The AgentManager creates and manages the agents
"""

import importlib
import logging

from .agent_platform import AgentPlatform
from .agents import Agent, provide

log = logging.getLogger(__name__)


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
        platform = AgentPlatform(machine_name=machine_name, loop=loop, regex=regex)
        manager = platform.create_agent(AgentManager, platform=platform)
        return manager

    def __init__(self, platform, *args, **kwargs):
        """Initialise the AgentManager
        """
        assert type(platform) is AgentPlatform, "Create the {} with its create method.".format(self.__class__.__name__)
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
