# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    19.08.2016
#   LICENSE:    MIT
#   FILE:       test_agent_manager.py
# =============================================================================

import asyncio
import logging
import os

import pytest
import serial.tools.list_ports

from hamas import Agent, AgentManager, Message, MessageTransportSystem
from hamas.transport import DictionaryContent

log = logging.getLogger(__name__)

TESTNOZIGBEE = 'HAMASNOZIGBEE' in os.environ.keys() and os.environ['HAMASNOZIGBEE'] == '1'
TESTNOTCONNECTED = not [fd for fd, p, i in serial.tools.list_ports.grep('/dev/ttyUSB')] and not TESTNOZIGBEE
TESTZIGBEE = not TESTNOZIGBEE and not TESTNOTCONNECTED


class TestAgentManager:
    """Test the AgentManager.
    """

    def test_created_with_init(self):
        """Test if the AgentManager can only be check_create by his factory
        """
        with pytest.raises(AssertionError):
            AgentManager(None, None, None)

    @pytest.mark.asyncio
    async def test_create(self, event_loop):
        """Test the creation of the AgentManager
        """
        ama = AgentManager.create('foo', event_loop)
        with pytest.raises(KeyError):
            AgentManager.create('foo', event_loop)
        assert ama.aid == 'foo/0'
        assert isinstance(ama._loop, asyncio.BaseEventLoop)
        assert type(ama._mts) is MessageTransportSystem
        assert ama.machine_name == 'foo'
        assert type(ama._white_pages) is dict
        assert ama.aid in ama._mts._local_connector
        ama.stop()
        del ama._platform._message_transport._platform_connector

    @pytest.mark.asyncio
    async def test_create_agent(self, am):
        # Create
        assert len(am.white_pages) == 1
        assert am.white_pages[am.aid] == 'AgentManager'
        assert am._platform.agents[am.aid] == am
        agent1 = am.create_agent(Agent)
        assert len(am.white_pages) == 2
        agent2 = am.create_agent(Agent)
        assert len(am.white_pages) == 3

        assert type(agent1) is Agent
        assert type(agent2) is Agent
        assert am._platform.agents[agent1.aid] is agent1
        assert am._platform.agents[agent2.aid] is agent2
        assert am.white_pages[agent1.aid] == 'Agent'
        assert am.white_pages[agent2.aid] == 'Agent'

        # Destroy
        am.destroy_agent(agent1.aid)
        assert len(am.white_pages) == 2
        assert agent1.aid not in am.white_pages
        assert agent1.aid not in am._platform.agents
        assert am.white_pages[agent2.aid] == 'Agent'
        assert am._platform.agents[agent2.aid] == agent2

        # Deregister
        agent3 = am.create_agent(Agent)
        assert len(am.white_pages) == 3
        assert len(am._platform.agents) == 3
        assert am.white_pages[agent3.aid] == 'Agent'
        assert am._platform.agents[agent3.aid] == agent3
        am._deregister(agent3.aid)
        assert len(am.white_pages) == 2
        assert len(am._platform.agents) == 3
        assert agent3.aid not in am.white_pages
        assert am._platform.agents[agent3.aid] == agent3

    @pytest.mark.asyncio
    async def test_communication(self, am):
        """Test if basic AgentManager functions are working
        """

        class MyAgent(Agent):
            """Docstring for MyAgent. """

            def __init__(self, *args, **kwargs):
                """TODO: to be defined1. """
                super(MyAgent, self).__init__(*args, **kwargs)
                self.message = None

            async def receive(self, message):
                self.message = message

        assert am.aid == 'foo/0'
        agent1 = am.create_agent(MyAgent)
        agent2 = am.create_agent(MyAgent)
        message1 = Message(sender=agent1.aid,
                           content=DictionaryContent({
                               'data': 'send this from agent 1 to agent 2'
                           }),
                           recipient=agent2.aid)

        await agent1.send(message1)
        assert agent2.message == message1

    @pytest.mark.asyncio
    async def test_get_agents(self, am):
        class MyAgent(Agent):
            pass

        agent1 = am.create_agent(Agent)
        agent2 = am.create_agent(MyAgent)
        agent3 = am.create_agent(MyAgent)

        addresses = am.get_agents('Agent')
        assert addresses == {'Agent': [agent1.aid]}

        addresses = am.get_agents('MyAgent')
        addresses['MyAgent'] = sorted(addresses['MyAgent'])
        assert addresses == {'MyAgent': [agent2.aid, agent3.aid]}

        addresses = am.get_agents()
        addresses['MyAgent'] = sorted(addresses['MyAgent'])
        assert addresses == {'AgentManager': [am.aid], 'Agent': [agent1.aid], 'MyAgent': [agent2.aid, agent3.aid]}

    @pytest.mark.asyncio
    async def test_request_myagent(self, am):

        class MyAgent(Agent):
            pass

        agent = am.create_agent(MyAgent)

        addresses = await agent.remote_process_call('get_agents', 'MyAgent', recipient=agent.am_aid)

        assert addresses == {
            'MyAgent': ['foo/1']
        }

    @pytest.mark.asyncio
    async def test_request_myagents(self, am):

        class MyAgent(Agent):
            pass

        agents = [am.create_agent(MyAgent) for _ in range(5)]
        addresses = await asyncio.gather(*[agent.remote_process_call(function='get_agents',
                                                                     agent_class_names='MyAgent',
                                                                     recipient=agent.am_aid)
                                           for agent in agents
                                           ])
        assert len(addresses) == 5
        for addr in addresses:
            addr['MyAgent'] = sorted(addr['MyAgent'])
            assert addr == {
                'MyAgent': ['foo/1', 'foo/2',
                            'foo/3', 'foo/4',
                            'foo/5']
            }

    @pytest.mark.asyncio
    async def test_request_agents_list(self, am):
        class MyAgent(Agent):
            pass

        class AnotherAgent(Agent):
            pass

        agents = [am.create_agent(MyAgent) for _ in range(5)]
        am.create_agent(AnotherAgent)

        addresses = await asyncio.gather(*[agent.remote_process_call(function='get_agents',
                                                                     agent_class_names=['MyAgent', 'AnotherAgent'],
                                                                     recipient=agent.am_aid)
                                           for agent in agents
                                           ])
        assert len(addresses) == 5
        for addr in addresses:
            addr['MyAgent'] = sorted(addr['MyAgent'])
            assert addr == {
                'AnotherAgent': ['foo/6'],
                'MyAgent': ['foo/1', 'foo/2',
                            'foo/3', 'foo/4',
                            'foo/5']
            }

    @pytest.mark.asyncio
    async def test_request_create_agent(self, am):

        agent = am.create_agent(Agent)
        assert len(am.white_pages) == 2
        address = await agent.remote_process_call(function='perform_create_agent',
                                                  agent_class_name='hamas.Agent',
                                                  recipient=agent.am_aid)
        assert address == 'foo/2'
        created_agent = am._platform.agents[address]
        assert type(created_agent) is Agent
        assert len(am.white_pages) == 3
        assert len(am._platform.agents) == 3
        assert address != am.aid
        assert address != agent.aid
        assert address == created_agent.aid
        assert address in am.white_pages
        assert address in am._platform.agents

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    class TestZigbee:
        # Run this on the local machine
        @pytest.mark.asyncio
        async def test_start(self, am):
            log.setLevel(logging.DEBUG)
            assert not am._machine._dummy_connector
            await am.start()
            agent = am.create_agent(Agent)
            known_machines = am.mts.other_machines
            assert known_machines == ['remote_machine']
            # remote_am_aid = known_machines[0] + '/0'
            remote_am_aid = known_machines[0]
            agent_aids = await agent.remote_process_call('get_agents', 'Agent', recipient=remote_am_aid, timeout=10)
            print(agent_aids)
            assert agent_aids == {'Agent': ['remote_machine/1', 'remote_machine/2']}

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    class TestZigbeeMac:
        # Run this on the local machine
        @pytest.mark.asyncio
        async def test_join_platform(self, machine_name, event_loop):
            am = AgentManager.create(machine_name, event_loop, 'cu.usbserial')
            try:
                log.setLevel(logging.DEBUG)
                await am.start()
                agent = am.create_agent(Agent)
                known_machines = am.mts.other_machines
                assert known_machines == ['remote_machine']
                remote_am_aid = known_machines[0] + '/0'
                agent_aids = await agent.remote_process_call('get_agents', 'Agent', address=remote_am_aid, timeout=10)
                print(agent_aids)
                assert agent_aids == {'Agent': ['remote_machine/1', 'remote_machine/2']}
            finally:
                am.stop()

    @pytest.mark.skipif(not TESTZIGBEE, reason="ZigBee module not available or disabled")
    class TestRemote:
        # Run this on the remote machine
        @pytest.mark.asyncio
        async def test_join_platform(self, event_loop):
            log.setLevel(logging.DEBUG)
            machine_name = 'remote_machine'
            am = AgentManager.create(machine_name=machine_name, loop=event_loop)
            try:
                am.create_agent(Agent)
                am.create_agent(Agent)
                await asyncio.sleep(1000)
            finally:
                am.stop()
