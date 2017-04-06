#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    07.07.2016
#   LICENSE:    MIT
#   FILE:       hello_world.py
# =============================================================================
"""The launcher script.
"""

import asyncio
import logging
import os

from hamas import Agent, AgentManager, config_logger

log = logging.getLogger(__name__)

config_logger(os.path.normpath('./logging.yaml'))


async def _print_agents(agent_manager):
    for ag in agent_manager.white_pages:
        print(ag)
    print("Stop the execution by pressing CTRL-C or stop via your IDE.")


def main():
    loop = asyncio.get_event_loop()
    platform_name = 'foo'
    regex = '/dev/ttyUSB'
    am = AgentManager.create(platform_name, loop, regex=regex)
    am.create_agent(Agent)
    task = asyncio.ensure_future(_print_agents(am))
    try:
        print("Running...")
        loop.run_forever()
    except KeyboardInterrupt:
        print("Stopping...")
        task.cancel()
        am.stop()
        # loop.run_until_complete(asyncio.wait(asyncio.Task.all_tasks()))
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()

if __name__ == '__main__':
    main()
    exit(0)
