from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Process

import dill
import orjson
import pika

from flux import CacheManager
from flux.config import Configuration
from flux.plugins import PluginManager
from flux.scheduler import Scheduler, TaskInfo
import boto3
from google.cloud import functions_v2
from flux.plugins import ExecutorPlugin


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
    def __init__(self, distributed_config: dict = None):
        self.distributed_config = distributed_config or {}
        self.scheduler = Scheduler()
        self.scheduler.start()
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=self.distributed_config.get('rabbitmq_host', 'localhost')
        ))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='flux_tasks', arguments={'x-max-priority': 10})
        self._start_workers()

    def _start_workers(self, num_workers: int = 2):
        for _ in range(num_workers):
            worker = Process(target=self._worker_loop, args=(self.connection,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)

    def _worker_loop(self, connection):
        channel = connection.channel()
        channel.queue_declare(queue='flux_tasks', arguments={'x-max-priority': 10})
        def callback(ch, method, properties, body):
            task_id, task, args, kwargs = dill.loads(body)
            try:
                result = task(*args, **kwargs)
                self._store_result(task_id, result)
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                self._store_result(task_id, None, e)
                ch.basic_ack(delivery_tag=method.delivery_tag)
        channel.basic_consume(queue='flux_tasks', on_message_callback=callback)
        channel.start_consuming()

    def _store_result(self, task_id: str, result: Any, error: Exception = None):
        # Store result in Redis or S3
        cache_manager = CacheManager.default()
        cache_manager.set(f"result_{task_id}", {'result': result, 'error': str(error) if error else None})

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
                self.channel.basic_publish(
                    exchange='',
                    routing_key='flux_tasks',
                    body=dill.dumps((task_id, scheduled_task.task, scheduled_task.args, scheduled_task.kwargs)),
                    properties=pika.BasicProperties(priority=scheduled_task.priority)
                )
                while True:
                    result = CacheManager.default().get(f"result_{task_id}")
                    if result:
                        self.scheduler.release_resources(scheduled_task.resource_requirements or {})
                        if result['error']:
                            raise Exception(result['error'])
                        return result['result']
                    await asyncio.sleep(0.01)
        return None

    def shutdown(self):
        self.connection.close()
        for worker in self.workers:
            worker.terminate()
        self.scheduler.shutdown()

class AWSLambdaExecutor(AbstractExecutor):
    def __init__(self):
        self.lambda_client = boto3.client('lambda')
        self.s3_client = boto3.client('s3')
        self.bucket = Configuration.get().settings.cloud.get('s3_bucket', 'flux-tasks')

    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        task_id = f"task-{id(task)}-{hash(str(args))}"
        serialized_task = dill.dumps((task, args, kwargs))
        self.s3_client.put_object(Bucket=self.bucket, Key=f"tasks/{task_id}", Body=serialized_task)
        response = self.lambda_client.invoke(
            FunctionName='flux-task-executor',
            Payload=orjson.dumps({'task_id': task_id, 'bucket': self.bucket})
        )
        result = orjson.loads(response['Payload'].read())
        if 'error' in result:
            raise Exception(result['error'])
        return dill.loads(self.s3_client.get_object(Bucket=self.bucket, Key=f"results/{task_id}")['Body'].read())

    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        return await asyncio.gather(*[self.execute(lambda: asyncio.run(task)) for task in tasks])

    def shutdown(self):
        pass

class GoogleCloudFunctionsExecutor(AbstractExecutor):
    def __init__(self):
        self.client = functions_v2.FunctionServiceClient()
        self.project = Configuration.get().settings.cloud.get('gcp_project', 'flux-project')
        self.bucket = Configuration.get().settings.cloud.get('gcs_bucket', 'flux-tasks')

    async def execute(self, task: Callable[..., Any], *args, **kwargs) -> Any:
        task_id = f"task-{id(task)}-{hash(str(args))}"
        serialized_task = dill.dumps((task, args, kwargs))
        # Upload to GCS (simplified)
        # Invoke Cloud Function and retrieve result
        return None  # Placeholder

    async def execute_parallel(self, tasks: List[Coroutine[Any, Any, Any]]) -> List[Any]:
        return await asyncio.gather(*[self.execute(lambda: asyncio.run(task)) for task in tasks])

    def shutdown(self):
        pass

class AWSLambdaPlugin(ExecutorPlugin):
    def __init__(self):
        super().__init__("aws_lambda", AWSLambdaExecutor)

class GoogleCloudFunctionsPlugin(ExecutorPlugin):
    def __init__(self):
        super().__init__("gcp_functions", GoogleCloudFunctionsExecutor)


def get_executor() -> AbstractExecutor:
    config = Configuration.get().settings.executor
    mode = config.execution_mode
    plugin_manager = PluginManager.default()

    # Check for plugin-based executor
    if mode not in ["local", "distributed"]:
        plugin = plugin_manager.get_plugin(mode)
        if isinstance(plugin, ExecutorPlugin):
            return plugin.executor_class()
        raise ValueError(f"Unknown execution mode or plugin: {mode}")

    if mode == "local":
        return LocalExecutor(max_workers=config.max_workers)
    elif mode == "distributed":
        return DistributedExecutor(distributed_config=config.distributed_config)
    raise ValueError(f"Unknown execution mode: {mode}")
