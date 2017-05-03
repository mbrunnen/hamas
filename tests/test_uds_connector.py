#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    26.04.2017
#   LICENSE:    MIT
#   FILE:       test_uds_connector.py
# =============================================================================

from hamas import USE_UDS
import pytest


class TestUnixConnector:
    @pytest.mark.skipif(USE_UDS == False, reason="UDS disabled.")
    def test_init(self, event_loop, platform_name):
        usbport = '/dev/ttyUSB'
        ports = [fd for fd, p, i in serial.tools.list_ports.grep(usbport)]
        assert len(ports) == 1
        zb = ZigBeeConnector(event_loop, platform_name)
        assert type(zb._serial) is serial.Serial
        assert isinstance(zb._loop, asyncio.BaseEventLoop)
        assert zb._callback is None
        zb.stop()
