#!/usr/bin/env python
# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    07.07.2016
#   LICENSE:    MIT
#   FILE:       __main__.py
# =============================================================================
"""The launcher script.
"""

import asyncio
import logging

from hamas import Agent, AgentManager

log = logging.getLogger(__name__)


async def _print_agents(agent_manager):
    for ag in agent_manager.white_pages:
        print(ag)


def main():
    loop = asyncio.get_event_loop()
    machine_name = 'foo'
    regex = '/dev/ttyUSB'
    am = AgentManager.create(machine_name, loop, regex=regex)
    agent = am.create_agent(Agent)
    task = asyncio.ensure_future(_print_agents(am))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        log.info("Stopping...")
        task.cancel()
        am.stop()
        loop.run_until_complete(asyncio.wait(asyncio.Task.all_tasks()))
    finally:
        loop.close()


if __name__ == '__main__':
    main()
    exit(0)
