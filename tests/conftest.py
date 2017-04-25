# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    01.08.2016
#   LICENSE:    MIT
#   FILE:	    conftest.py
# =============================================================================
import tempfile

import pytest

from hamas import AgentManager, ZigBeeConnector, AgentPlatform, \
    PlatformConnector


@pytest.fixture
def platform_name():
    return 'foo'


@pytest.fixture(scope="function")
def am(event_loop, platform_name):
    # Create an agent manager for each test.
    agent_manager = AgentManager.create(platform_name, event_loop)
    yield agent_manager
    agent_manager.stop()
    print("\n\tdelete manager\n")


@pytest.fixture(scope="function")
def ap(event_loop, platform_name):
    # Create a agent platform for each test.
    platform = AgentPlatform(platform_name, event_loop)
    yield platform
    platform.stop()
    del PlatformConnector._platforms[platform_name]


@pytest.fixture
def mts(ap):
    # Create a message transport system for each test.
    return ap._message_transport


@pytest.fixture
def tmpfile():
    return tempfile.NamedTemporaryFile()


@pytest.fixture
def zb(event_loop, platform_name):
    zigbee = ZigBeeConnector(event_loop, platform_name)
    yield zigbee
    zigbee.stop()


@pytest.fixture
def router_addr():
    # retrieve the router address from XCTU
    return '142A'


@pytest.fixture
def end_dev_addr():
    # retrieve the end device address from XCTU
    return 'D185'
