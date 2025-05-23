from __future__ import annotations
import pytest
import asyncio
from flux.executors import LocalExecutor, DistributedExecutor, get_executor
from flux.config import Configuration

@pytest.mark.asyncio
async def test_local_executor():
    executor = LocalExecutor(max_workers=2)
    async def sample_task(x: int) -> int:
        return x * 2
    result = await executor.execute(sample_task, 5)
    assert result == 10
    
    tasks = [sample_task(i) for i in range(3)]
    results = await executor.execute_parallel(tasks)
    assert results == [0, 2, 4]
    
    executor.shutdown()

@pytest.mark.asyncio
async def test_distributed_executor():
    executor = DistributedExecutor()
    async def sample_task(x: int) -> int:
        return x * 2
    result = await executor.execute(sample_task, 5)
    assert result == 10
    
    tasks = [sample_task(i) for i in range(3)]
    results = await executor.execute_parallel(tasks)
    assert results == [0, 2, 4]
    
    executor.shutdown()

@pytest.mark.asyncio
async def test_executor_config_local():
    Configuration().override(executor={"execution_mode": "local", "max_workers": 2})
    executor = get_executor()
    assert isinstance(executor, LocalExecutor)
    
    async def sample_task(x: int) -> int:
        return x * 2
    result = await executor.execute(sample_task, 5)
    assert result == 10
    executor.shutdown()

@pytest.mark.asyncio
async def test_executor_config_distributed():
    Configuration().override(executor={"execution_mode": "distributed", "distributed_config": {"num_workers": 2}})
    executor = get_executor()
    assert isinstance(executor, DistributedExecutor)
    
    async def sample_task(x: int) -> int:
        return x * 2
    result = await executor.execute(sample_task, 5)
    assert result == 10
    executor.shutdown()