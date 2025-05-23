from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process, Queue
from flux.config import Configuration

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
    
    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: task(*args, **kwargs))
    
    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        return await asyncio.gather(*tasks)
    
    def shutdown(self):
        self.executor.shutdown()

class DistributedExecutor(AbstractExecutor):
    """Generic distributed executor with in-memory queue (placeholder for queuing system)."""
    
    def __init__(self, distributed_config: dict = None):
        self.task_queue = Queue()  # In-memory queue for tasks
        self.result_queue = Queue()  # In-memory queue for results
        self.workers = []
        self.distributed_config = distributed_config or {}
        self._start_workers()
    
    def _start_workers(self, num_workers: int = 2):
        """Start worker processes to process tasks."""
        for _ in range(num_workers):
            worker = Process(target=self._worker_loop, args=(self.task_queue, self.result_queue))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self, task_queue: Queue, result_queue: Queue):
        """Worker loop to process tasks from the queue."""
        while True:
            task_data = task_queue.get()
            if task_data is None:  # Sentinel for shutdown
                break
            task_id, task, args, kwargs = task_data
            try:
                result = task(*args, **kwargs)
                result_queue.put((task_id, result, None))
            except Exception as e:
                result_queue.put((task_id, None, e))
    
    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        task_id = f"task-{id(task)}-{hash(str(args))}"
        self.task_queue.put((task_id, task, args, kwargs))
        
        while True:
            if not self.result_queue.empty():
                result_id, result, error = self.result_queue.get()
                if result_id == task_id:
                    if error:
                        raise error
                    return result
            await asyncio.sleep(0.01)  # Yield control
    
    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        results = []
        for task in tasks:
            task_func = lambda: asyncio.run(task)  # Convert coroutine to sync function
            result = await self.execute(task_func)
            results.append(result)
        return results
    
    def shutdown(self):
        """Shutdown worker processes."""
        for _ in self.workers:
            self.task_queue.put(None)  # Send shutdown signal
        for worker in self.workers:
            worker.join()
        self.task_queue.close()
        self.result_queue.close()

def get_executor() -> AbstractExecutor:
    """Factory function to get the configured executor."""
    config = Configuration.get().settings.executor
    mode = config.execution_mode
    if mode == "local":
        return LocalExecutor(max_workers=config.max_workers)
    elif mode == "distributed":
        return DistributedExecutor(distributed_config=config.distributed_config)
    raise ValueError(f"Unknown execution mode: {mode}")