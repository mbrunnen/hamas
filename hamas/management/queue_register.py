# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    17.10.2016
#   LICENSE:    MIT
#   FILE:       queue_register.py
# =============================================================================
"""Queue register for handling incoming messages or frames
"""

import asyncio
import collections

import logging

log = logging.getLogger(__name__)


class QueueRegister(object):
    """A dictionary containing asyncio queues.
        Args:
            _url_queue(dict): The dictionary with the queues
    """

    def __init__(self):
        self._queues = collections.defaultdict(asyncio.Queue)
        self._queue_futs = collections.defaultdict(asyncio.Future)

    def __len__(self):
        return len(self._queues)

    def __contains__(self, item):
        return item in self._queues

    def new_queue(self, qid, queue_consumer):
        log.debug("Started a new Queue with ID {}. There are now {:d} queues in this register.".format(qid, len(self._queues) + 1))
        assert qid not in self
        queue_fut = asyncio.Future()
        self._queue_futs[qid] = queue_fut
        queue = asyncio.Queue()
        self._queues[qid] = queue
        asyncio.ensure_future(queue_consumer)
        if len(self._queues) > 100:
            log.warning("The list of queues is getting long: {:d}".format(len(self._queues)))
        return queue_fut

    async def put(self, qid, item):
        assert qid in self
        await self._queues[qid].put(item)

    async def get(self, qid):
        assert qid in self
        return await self._queues[qid].get()

    def task_done(self, qid):
        self._queues[qid].task_done()

    def set_result(self, qid, result):
        log.debug('Finished queue {}.'.format(qid))
        # the queue is now considered finished
        self._queues.pop(qid)
        queue_fut = self._queue_futs.pop(qid)
        # in the case there are more than one consumer
        queue_fut.set_result(result)
