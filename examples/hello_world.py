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

from hamas import Agent, AgentManager, Configuration, config_logger

# Configurate the logger
config_logger('hello_world_logging.yaml')

# get the logger for this file
log = logging.getLogger(__name__)


async def _print_agents(agent_manager):
    print("Stop the execution by pressing CTRL-C or stop via your IDE.")
    while True:
        for ag in agent_manager.white_pages:
            log.info(ag)
        await asyncio.sleep(5)


def main():
    # conf = Configuration()
    conf = Configuration('hello_world.conf')
    loop = asyncio.get_event_loop()
    am = AgentManager.create(loop, conf)
    am.create_agent(Agent)
    asyncio.ensure_future(am.start())
    task = asyncio.ensure_future(_print_agents(am))
    try:
        print("Running...")
        loop.run_forever()
    except KeyboardInterrupt:
        print("Stopping...")
        task.cancel()
        am.stop()
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == '__main__':
    main()
    exit(0)
