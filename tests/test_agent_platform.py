# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    01.12.2016
#   LICENSE:    MIT
#   FILE:       test_agent_platform.py
# =============================================================================

import pytest

from hamas import Agent


class TestAgentPlatform:
    def test_generate_aid_num(self, ap):
        for i, a in enumerate(ap._name_gen):
            assert a == i
            if i == 100:
                break
        ap._free_names.append(50)
        assert next(ap._name_gen) == 50
        assert next(ap._name_gen) == 101

    @pytest.mark.asyncio
    async def test_create_agent(self, ap):
        """Test the agent creation of agents with the AgentPlatform
        """

        agents = []
        for i in range(5):
            assert len(ap.agents) == i
            agent = ap.create_agent(Agent)
            assert agent.aid == 'foo/' + str(i)
            assert agent.aid in ap.agents
            assert agent == ap.agents[agent.aid]
            agents.append(agent)

        assert len(ap.agents) == 5
        ap.destroy_agent(agents[2].aid)
        assert len(ap.agents) == 4
        assert agents[2].aid not in ap.agents

        agent4 = ap.create_agent(Agent)
        assert agent4.aid == 'foo/2'
        assert agent4.aid in ap.agents
        assert agent4 == ap.agents[agent4.aid]
        assert len(ap.agents) == 5

    @pytest.mark.asyncio
    async def test_destroy(self, ap):
        # Create
        assert len(ap.agents) == 0
        agent1 = ap.create_agent(Agent)
        assert len(ap.agents) == 1
        agent2 = ap.create_agent(Agent)
        assert len(ap.agents) == 2
        assert type(agent1) is Agent
        assert type(agent2) is Agent
        assert ap.agents[agent1.aid] is agent1
        assert ap.agents[agent2.aid] is agent2
        assert ap.agents[agent1.aid] is not ap.agents[agent2.aid]

        # Destroy
        ap.destroy_agent(agent1.aid)
        assert agent1.aid not in ap.agents
        assert agent2.aid in ap.agents
        assert len(ap.agents) == 1
        assert ap.agents[agent2.aid] == agent2
