# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    21.10.16
#   LICENSE:    MIT
#   FILE:       test_queue_register.py
# =============================================================================

import pytest

from hamas.management import QueueRegister


class TestQueueregister:
    @pytest.mark.asyncio
    async def test_new_queue(self):
        async def queue_consumer(q_id):
            result = await queues.get(q_id)
            queues.task_done(q_id)
            queues.set_result(q_id, result)

        qid = 'test'

        queues = QueueRegister()
        assert queues._queues == {}
        assert queues._queue_futs == {}

        assert qid not in queues
        q_fut = queues.new_queue(qid, queue_consumer(qid))
        assert queues._queues != {}
        assert queues._queue_futs == {'test': q_fut}
        assert qid in queues
        await queues.put(qid, 'the result')
        q_result = await q_fut
        assert qid not in queues
        assert queues._queues == {}
        assert queues._queue_futs == {}
        assert q_result == 'the result'
