# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:	    Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    01.08.2016
#   LICENSE:    MIT
#   FILE:	    conftest.py
# =============================================================================
"""Test fixtures
"""

import tempfile

import pytest

from hamas import AgentManager, ZigBeeConnector, AgentPlatform


@pytest.fixture
def machine_name():
    return 'foo'


@pytest.fixture
def am(event_loop, machine_name):
    """Create an instance of an machine_manager for each test."""
    machine_manager = AgentManager.create(machine_name, event_loop)
    yield machine_manager
    machine_manager.stop()
    del machine_manager._platform._message_transport._platform_connector


@pytest.fixture
def ap(event_loop, machine_name):
    """Create an instance of an machine_manager for each test."""
    platform = AgentPlatform(machine_name, event_loop)
    yield platform
    platform.stop()
    del platform


@pytest.fixture
def mts(ap):
    """Create an instance of MessageTransportSystem for each test."""
    return ap._message_transport


@pytest.fixture
def tmpfile():
    return tempfile.NamedTemporaryFile()


@pytest.fixture
def zb(event_loop, machine_name):
    zigbee = ZigBeeConnector(event_loop, machine_name)
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
