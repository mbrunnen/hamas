# -*- coding: utf-8 -*-
# =============================================================================
#   AUTHOR:     Manoel Brunnen, manoel.brunnen@gmail.com
#   CREATED:    27.07.2016
#   LICENSE:    MIT
#   FILE:       test_jobs.py
# =============================================================================
"""Test the class Job
"""

import asyncio
import random
import time
from asyncio import gather
from asyncio import wait

import pytest


# noinspection PyShadowingNames
class TestJob:
    """Try basic asyncio function, not relevant for hamas
    """

    @pytest.mark.asyncio
    async def test_factory(self, event_loop):
        """Test the Job factory
        """

        async def coro():
            pass

        assert event_loop.get_task_factory() is None

        job = asyncio.ensure_future(coro())
        assert type(job) is asyncio.Task
        await job

    @pytest.mark.asyncio
    async def test_cancel(self, event_loop):
        """Test to stop a job, while it's running
        """

        async def my_func():
            pass

        job = event_loop.create_task(my_func())
        cancel_successful = job.cancel()

        assert cancel_successful
        with pytest.raises(asyncio.CancelledError):
            await job

    @pytest.mark.asyncio
    async def test_result(self, event_loop):
        """Test if the job result is correct
        """

        async def my_func(x, y):
            return x / y

        random.seed(1)
        a = random.random()
        b = random.random()

        job = event_loop.create_task(my_func(a, b))

        result = await job
        assert result == a / b
        assert job.done()

    @pytest.mark.asyncio
    async def test_result_not_ready(self, event_loop):
        """Test if a Exception is thrown if the Job result is not ready
        """

        async def my_func():
            pass

        job = event_loop.create_task(my_func())
        with pytest.raises(asyncio.InvalidStateError):
            await job.result()
        assert not job.done()
        job.cancel()

    @pytest.mark.asyncio
    async def test_cancel_if_done(self, event_loop):
        """Test to stop a job when it's already done
        """

        async def my_func(duration):
            await asyncio.sleep(duration)

        task_time = 0.1
        job = event_loop.create_task(my_func(task_time))
        before = time.monotonic()
        assert not job.done()
        await asyncio.sleep(0.2)
        after = time.monotonic()
        cancel_successful = job.cancel()

        assert job.done()
        assert after - before > task_time
        assert not cancel_successful

    @pytest.mark.asyncio
    async def test_gather(self, event_loop):
        """Test gathering results from the job list
        """

        async def my_coro(x):
            await asyncio.sleep(random.random() / 10)
            return x * x

        n_jobs = 5

        jobs = [asyncio.ensure_future(my_coro(i), loop=event_loop) for i in range(
            n_jobs)]

        assert len(jobs) == n_jobs

        results = await gather(*jobs)
        assert len(results) == n_jobs

        assert results == [j * j for j in range(n_jobs)]

    @pytest.mark.asyncio
    async def test_wait(self, event_loop):
        """Test awaiting a job list
        """
        my_list = list()

        async def my_coro(x):
            await asyncio.sleep(random.random() / 10)
            my_list.append(x * x)

        n_jobs = 5

        jobs = [asyncio.ensure_future(my_coro(i), loop=event_loop) for i in range(n_jobs)]

        assert len(jobs) == n_jobs

        await wait(jobs)
        assert len(my_list) == n_jobs

        for i in range(n_jobs):
            assert i * i in my_list
