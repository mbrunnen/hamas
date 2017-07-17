# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    30.11.2016
#   LICENSE:    MIT
#   FILE:       management.py
# =============================================================================
"""The agent management module contains the two basic classes for the
management of the agents: The :class:`AgentManager` and the
:class:`AgentPlatform`. The :meth:`AgentManager.create` classmethod is used to
initiate the whole system, including the :class:`AgentManager` and the
:class:`AgentPlatform`.
"""

import importlib
import itertools
import logging
import string

from .agents import Agent, provide
from .transport.message_transport import MessageTransportSystem

log = logging.getLogger(__name__)


class AgentPlatform(object):
    """The :class:`AgentPlatform` contains all the elements of a multi-agent
    system. This includes the message transport system and all the agents.

    Args:
        loop (asyncio.BaseEventLoop): The loop in which the platform should
            run.
        name (str): The unique name of the platform.
        has_platform (bool): True if the :class:`PlatformConnector` should
            be used.
        has_zigbee (bool): True if the :class:`ZigBeeConnector` should be
            used.
        has_mqtt (bool): True if the :class:`MqttConnector` should be
            used.
        has_uds (bool): True if the class:`UnixConnector` should be
            used.
        regex (str): The device path of the ZigBee module.
        broker (str): The address of the MQTT broker.
        update_interval (int,float): The interval of updating the
            :class:`.MessageTransportSystem`.
    """
    _allowed_chars = '_' + string.ascii_letters + string.digits

    def __init__(self, loop, name, has_platform, has_zigbee, has_mqtt,
                 has_uds, regex, broker, update_interval=60):
        def generate_name():
            gen_new = itertools.count()
            while True:
                for i in self._free_names:
                    self._free_names.remove(i)
                    yield i
                yield next(gen_new)

        assert set(name) <= set(
            self._allowed_chars
        ), "Only {} characters are allowed as platform name.".format(
            self._allowed_chars)
        self._loop = loop
        self._name = name
        self._message_transport = MessageTransportSystem(
            platform=self,
            has_platform=has_platform,
            has_zigbee=has_zigbee,
            has_mqtt=has_mqtt,
            has_uds=has_uds,
            regex=regex,
            broker=broker,
            update_interval=update_interval)
        self.__agents = dict()
        self._last_num = 0
        self._free_names = list()
        self._name_gen = generate_name()

    async def start(self):
        await self._message_transport.start()

    def stop(self):
        self._message_transport.stop()

    @property
    def name(self):
        """str: The name of the platform."""
        return self._name

    @property
    def loop(self):
        """BaseEventLoop: The :class:`asyncio.BaseEventLoop` in which
        the coroutines of the application will run.
        """
        return self._loop

    @property
    def agents(self):
        return self.__agents

    def create_agent(self, agent_class, *args, **kwargs):
        """Create an agent

        Args:
            agent_class (class): Passes the class of the required Agent
            args: Passes the arguments to the constructor of the agent
                class.
            kwargs: Passes the keyword arguments to the constructor of
                the agent class

        """
        assert issubclass(agent_class, Agent)
        agent_name = str(next(self._name_gen))
        aid = self._name + '/' + agent_name
        agent = agent_class(
            *args, aid=aid, mts=self._message_transport, **kwargs)
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
    """Initial :class:`hamas.agents.Agent` running which creates, runs and
    manages the agents.

    Args:
        has_platform (bool): True if the :class:`PlatformConnector` should
            be used.
        has_zigbee (bool): True if the :class:`ZigBeeConnector` should be
            used.
        has_mqtt (bool): True if the :class:`MqttConnector` should be
            used.
        has_uds (bool): True if the class:`UnixConnector` should be
            used.

    Attributes:
        _white_pages (dict): Dictionary which contains the agent description,
            actually the class name.
        _platform (AgentPlatform): The platform, on which the
            :class:`AgentManager` is managing the agents.

    """
    __in_create = False

    @classmethod
    def create(cls, loop, config):
        """Factory function which instantiates a AgentManager agent.

        Do not instantiate the AgentManager directly. It is a special agent,
        which has no ID given, so it will create it's own ID.  Also it will
        create a :class:`hamas.MessageTransportSystem`.

        Arguments:
            loop (BaseEventLoop): The event loop.
            config(Configuration): A configuration, which is an instance of
                :class:`hamas.Configuration`.

        Returns:
            AgentManager

        """
        platform = AgentPlatform(loop=loop,
                                 name=config.machine_name,
                                 has_platform=config.use_platform,
                                 has_zigbee=config.use_zigbee,
                                 has_mqtt=config.use_mqtt,
                                 has_uds=config.use_uds,
                                 regex=config.device,
                                 broker=config.broker)
        manager = platform.create_agent(AgentManager, platform=platform)
        return manager

    def __init__(self, platform, *args, **kwargs):
        assert type(
            platform
        ) is AgentPlatform, "Create the {} with its create method.".format(
            self.__class__.__name__)
        super(AgentManager, self).__init__(*args, **kwargs)
        self._platform = platform
        self._white_pages = dict()
        self._register(self)

    @property
    def other_platforms(self):
        return self._mts.other_platforms

    async def start(self):
        """This method starts all the tasks of the multi-agent system. This
        includes sending network discovery beacons.

        """
        await self._platform.start()

    def stop(self):
        """ Stops all the tasks of the multi-agent system.
        """
        self._platform.stop()

    async def wait_for_zigbee(self):
        """This couroutine blocks until other participants are found in the
        ZigBee network and is used for testing purposes.
        """
        await self._mts.wait_for_zigbee()

    @property
    def white_pages(self):
        """dict: Dictionary which contains the agent description, actually the
        class name.
        """
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
        mod = importlib.import_module(path)
        agent_class = getattr(mod, class_name)
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
