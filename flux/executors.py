from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Queue
from flux.config import Configuration
from flux.scheduler import Scheduler, TaskInfo


class AbstractExecutor(ABC):
    """Abstract base class for task executors."""

    @abstractmethod
    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a single task."""
        pass

    @abstractmethod
    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        """Execute multiple tasks in parallel."""
        pass

    @abstractmethod
    def shutdown(self):
        """Clean up executor resources."""
        pass


class LocalExecutor(AbstractExecutor):
    """Executor for local task execution using threads."""

    def __init__(self, max_workers: int = None):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.scheduler = Scheduler()
        self.scheduler.start()

    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        task_info = TaskInfo(
            task_id=f"task-{id(task)}-{hash(str(args))}",
            task=task,
            args=args,
            kwargs=kwargs,
            priority=kwargs.pop("priority", Configuration.get().settings.executor.default_priority),
            deadline=kwargs.pop("deadline", None),
            resource_requirements=kwargs.pop("resource_requirements", None),
            schedule=kwargs.pop("schedule", None)
        )
        await self.scheduler.schedule_task(task_info)
        if not task_info.schedule:
            scheduled_task = await self.scheduler.get_next_task()
            if scheduled_task:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    lambda: scheduled_task.task(*scheduled_task.args, **scheduled_task.kwargs)
                )
                self.scheduler.release_resources(scheduled_task.resource_requirements or {})
                return result
        return None

    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        results = []
        for task in tasks:
            task_func = lambda: asyncio.run(task)
            result = await self.execute(task_func)
            if result is not None:
                results.append(result)
        return results

    def shutdown(self):
        self.executor.shutdown()
        self.scheduler.shutdown()


class DistributedExecutor(AbstractExecutor):
    """Generic distributed executor with in-memory queue."""

    def __init__(self, distributed_config: dict = None):
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.workers = []
        self.distributed_config = distributed_config or {}
        self.scheduler = Scheduler()
        self.scheduler.start()
        self._start_workers()

    def _start_workers(self, num_workers: int = 2):
        for _ in range(num_workers):
            worker = Process(target=self._worker_loop, args=(self.task_queue, self.result_queue))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self, task_queue: Queue, result_queue: Queue):
        while True:
            task_data = task_queue.get()
            if task_data is None:
                break
            task_id, task, args, kwargs = task_data
            try:
                result = task(*args, **kwargs)
                result_queue.put((task_id, result, None))
            except Exception as e:
                result_queue.put((task_id, None, e))

    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        task_id = f"task-{id(task)}-{hash(str(args))}"
        task_info = TaskInfo(
            task_id=task_id,
            task=task,
            args=args,
            kwargs=kwargs,
            priority=kwargs.pop("priority", Configuration.get().settings.executor.default_priority),
            deadline=kwargs.pop("deadline", None),
            resource_requirements=kwargs.pop("resource_requirements", None),
            schedule=kwargs.pop("schedule", None)
        )
        await self.scheduler.schedule_task(task_info)
        if not task_info.schedule:
            scheduled_task = await self.scheduler.get_next_task()
            if scheduled_task:
                self.task_queue.put((task_id, scheduled_task.task, scheduled_task.args, scheduled_task.kwargs))
                while True:
                    if not self.result_queue.empty():
                        result_id, result, error = self.result_queue.get()
                        if result_id == task_id:
                            self.scheduler.release_resources(scheduled_task.resource_requirements or {})
                            if error:
                                raise error
                            return result
                    await asyncio.sleep(0.01)
        return None

    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        results = []
        for task in tasks:
            task_func = lambda: asyncio.run(task)
            result = await self.execute(task_func)
            if result is not None:
                results.append(result)
        return results

    def shutdown(self):
        for _ in self.workers:
            self.task_queue.put(None)
        for worker in self.workers:
            worker.join()
        self.task_queue.close()
        self.result_queue.close()
        self.scheduler.shutdown()


def get_executor() -> AbstractExecutor:
    config = Configuration.get().settings.executor
    mode = config.execution_mode
    if mode == "local":
        return LocalExecutor(max_workers=config.max_workers)
    elif mode == "distributed":
        return DistributedExecutor(distributed_config=config.distributed_config)
    raise ValueError(f"Unknown execution mode: {mode}")