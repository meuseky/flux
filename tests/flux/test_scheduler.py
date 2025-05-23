from __future__ import annotations
import pytest
import asyncio
import httpx
from datetime import datetime, timedelta
from flux.scheduler import Scheduler, TaskInfo
from flux.config import Configuration
from flux.context import WorkflowExecutionContext


@pytest.mark.asyncio
async def test_priority_scheduling():
    scheduler = Scheduler()
    scheduler.start()

    async def sample_task(x: int) -> int:
        return x * 2

    task1 = TaskInfo(task_id="t1", task=sample_task, args=(5,), kwargs={}, priority=1)
    task2 = TaskInfo(task_id="t2", task=sample_task, args=(10,), kwargs={}, priority=10)

    await scheduler.schedule_task(task2)
    await scheduler.schedule_task(task1)

    next_task = await scheduler.get_next_task()
    assert next_task.task_id == "t1"

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_resource_allocation_with_gpu():
    Configuration().override(executor={"available_cpu": 2, "available_memory": 8, "available_gpu": 1})
    scheduler = Scheduler()
    scheduler.start()

    async def sample_task(x: int) -> int:
        return x * 2

    task1 = TaskInfo(
        task_id="t1",
        task=sample_task,
        args=(5,),
        kwargs={},
        priority=1,
        resource_requirements={"cpu": 1, "memory": 4, "gpu": 1}
    )
    task2 = TaskInfo(
        task_id="t2",
        task=sample_task,
        args=(10,),
        kwargs={},
        priority=1,
        resource_requirements={"cpu": 1, "memory": 4, "gpu": 1}
    )

    await scheduler.schedule_task(task1)
    await scheduler.schedule_task(task2)

    next_task = await scheduler.get_next_task()
    assert next_task.task_id == "t1"

    next_task = await scheduler.get_next_task()
    assert next_task is None  # No GPU available

    scheduler.release_resources({"cpu": 1, "memory": 4, "gpu": 1})
    next_task = await scheduler.get_next_task()
    assert next_task.task_id == "t2"

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_cron_scheduling():
    scheduler = Scheduler()
    scheduler.start()

    async def sample_task(x: int) -> int:
        return x * 2

    task = TaskInfo(
        task_id="t1",
        task=sample_task,
        args=(5,),
        kwargs={},
        priority=1,
        schedule="*/1 * * * *"
    )

    await scheduler.schedule_task(task)
    await asyncio.sleep(1)
    next_task = await scheduler.get_next_task()
    assert next_task.task_id == "t1"

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_http_trigger():
    scheduler = Scheduler()
    scheduler.start()

    async def sample_task(x: int) -> int:
        return x * 2

    task = TaskInfo(
        task_id="t1",
        task=sample_task,
        args=(5,),
        kwargs={},
        priority=1,
        event_trigger={"type": "http", "endpoint": "/webhook/t1"}
    )

    await scheduler.schedule_task(task)

    # Simulate HTTP request
    async with httpx.AsyncClient(app=scheduler.fastapi_app, base_url="http://test") as client:
        response = await client.post("/webhook/t1", json={"data": "test"})
        assert response.status_code == 200

    await asyncio.sleep(0.1)
    next_task = await scheduler.get_next_task()
    assert next_task.task_id == "t1"

    ctx = await WorkflowExecutionContext.get()
    trigger_event = next(e for e in ctx.events if e.type == ExecutionEventType.TASK_TRIGGERED)
    assert trigger_event.value["endpoint"] == "/webhook/t1"

    scheduler.shutdown()


@pytest.mark.asyncio
async def test_kubernetes_trigger():
    scheduler = Scheduler()
    scheduler.start()

    async def sample_task(x: int) -> int:
        return x * 2

    task = TaskInfo(
        task_id="t1",
        task=sample_task,
        args=(5,),
        kwargs={},
        priority=1,
        event_trigger={"type": "kubernetes", "namespace": "default", "cronjob": "task1"}
    )

    await scheduler.schedule_task(task)
    # Placeholder: Verify logging or future Kubernetes API call
    scheduler.shutdown()