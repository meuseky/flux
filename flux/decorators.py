from __future__ import annotations
import asyncio
import inspect
import time
from functools import wraps
from typing import Any, Callable, TypeVar, Optional, Dict
from datetime import datetime
from flux.cache import CacheManager
from flux.context import WorkflowExecutionContext
from flux.context_managers import ContextManager
from flux.errors import ExecutionError, ExecutionTimeoutError, PauseRequested, RetryError
from flux.events import ExecutionEvent, ExecutionEventType
from flux.output_storage import OutputStorage
from flux.secret_managers import SecretManager
from flux.utils import make_hashable, maybe_awaitable
from flux.executors import get_executor
from flux.scheduler import Scheduler, TaskInfo
from flux.config import Configuration

F = TypeVar("F", bound=Callable[..., Any])


def get_func_args(func: Callable, args: tuple) -> dict:
    arg_names = inspect.getfullargspec(func).args
    arg_values: list[Any] = []
    for arg in args:
        if isinstance(arg, workflow):
            arg_values.append(arg.name)
        elif inspect.isclass(type(arg)) and isinstance(arg, Callable):
            arg_values.append(arg)
        elif isinstance(arg, Callable):
            arg_values.append(arg.__name__)
        elif isinstance(arg, list):
            arg_values.append(tuple(arg))
        else:
            arg_values.append(arg)
    return dict(zip(arg_names, arg_values))


class workflow:
    @staticmethod
    def with_options(name: str | None = None, secret_requests: list[str] = [],
                     output_storage: OutputStorage | None = None) -> Callable[[F], workflow]:
        def wrapper(func: F) -> workflow:
            return workflow(func=func, name=name, secret_requests=secret_requests, output_storage=output_storage)

        return wrapper

    def __init__(self, func: F, name: str | None = None, secret_requests: list[str] = [],
                 output_storage: OutputStorage | None = None):
        self._func = func
        self.name = name if name else func.__name__
        self.secret_requests = secret_requests
        self.output_storage = output_storage
        wraps(func)(self)

    async def __call__(self, ctx: WorkflowExecutionContext, *args) -> Any:
        if ctx.finished:
            return ctx
        self.id = f"{ctx.name}_{ctx.execution_id}"
        if ctx.paused:
            ctx.events.append(ExecutionEvent(type=ExecutionEventType.WORKFLOW_RESUMED, source_id=self.id, name=ctx.name,
                                             value=ctx.input))
        elif not ctx.started:
            ctx.events.append(ExecutionEvent(ExecutionEventType.WORKFLOW_STARTED, self.id, ctx.name, ctx.input))
        try:
            token = WorkflowExecutionContext.set(ctx)
            output = await maybe_awaitable(self._func(ctx))
            WorkflowExecutionContext.reset(token)
            ctx.events.append(
                ExecutionEvent(type=ExecutionEventType.WORKFLOW_COMPLETED, source_id=self.id, name=ctx.name,
                               value=self.output_storage.store(self.id, output) if self.output_storage else output))
        except PauseRequested as ex:
            ctx.events.append(ExecutionEvent(type=ExecutionEventType.WORKFLOW_PAUSED, source_id=self.id, name=ctx.name,
                                             value=ex.name))
        except ExecutionError as ex:
            ctx.events.append(
                ExecutionEvent(type=ExecutionEventType.WORKFLOW_FAILED, source_id=self.id, name=ctx.name, value=ex))
        except Exception as ex:
            ctx.events.append(
                ExecutionEvent(type=ExecutionEventType.WORKFLOW_FAILED, source_id=self.id, name=ctx.name, value=ex))
        ContextManager.default().save(ctx)
        return ctx

    def run(self, *args, **kwargs) -> WorkflowExecutionContext:
        ctx = ContextManager.default().get(
            kwargs["execution_id"]) if "execution_id" in kwargs else WorkflowExecutionContext(self.name, *args)
        return asyncio.run(self(ctx))


class TaskMetadata:
    def __init__(self, task_id: str, task_name: str):
        self.task_id = task_id
        self.task_name = task_name

    def __repr__(self):
        return f"TaskMetadata(task_id={self.task_id}, task_name={self.task_name})"


class task:
    @staticmethod
    def with_options(
            cache: bool = False,
            cache_ttl: Optional[int] = None,
            cache_version: Optional[str] = None,
            name: Optional[str] = None,
            secret_requests: list[str] = [],
            output_storage: OutputStorage | None = None,
            priority: int = 10,
            timeout: int = 0,
            deadline: Optional[datetime] = None,
            resource_requirements: Optional[Dict[str, Any]] = None,
            schedule: Optional[str] = None,
            event_trigger: Optional[Dict[str, str]] = None,
            metadata: bool = False,
            fallback: Optional[Callable] = None,
            rollback: Optional[Callable] = None
    ) -> Callable[[F], task]:
        def wrapper(func: F) -> task:
            return task(
                func=func,
                cache=cache,
                cache_ttl=cache_ttl,
                cache_version=cache_version,
                name=name,
                secret_requests=secret_requests,
                output_storage=output_storage,
                priority=priority,
                timeout=timeout,
                deadline=deadline,
                resource_requirements=resource_requirements,
                schedule=schedule,
                event_trigger=event_trigger,
                metadata=metadata,
                fallback=fallback,
                rollback=rollback
            )

        return wrapper

    def __init__(
            self,
            func: F,
            cache: bool = False,
            cache_ttl: Optional[int] = None,
            cache_version: Optional[str] = None,
            name: Optional[str] = None,
            secret_requests: list[str] = [],
            output_storage: OutputStorage | None = None,
            priority: int = 10,
            timeout: int = 0,
            deadline: Optional[datetime] = None,
            resource_requirements: Optional[Dict[str, Any]] = None,
            schedule: Optional[str] = None,
            event_trigger: Optional[Dict[str, str]] = None,
            metadata: bool = False,
            fallback: Optional[Callable] = None,
            rollback: Optional[Callable] = None
    ):
        self._func = func
        self.name = name if name else func.__name__
        self.secret_requests = secret_requests
        self.output_storage = output_storage
        self.priority = priority
        self.timeout = timeout
        self.deadline = deadline
        self.resource_requirements = resource_requirements
        self.schedule = schedule
        self.event_trigger = event_trigger
        self.metadata = metadata
        self.cache = cache
        self.cache_ttl = cache_ttl
        self.cache_version = cache_version
        self.fallback = fallback
        self.rollback = rollback
        wraps(func)(self)

    async def __call__(self, *args, **kwargs) -> Any:
        task_args = get_func_args(self._func, args)
        full_name = self.name.format(**task_args)
        task_id = f"{full_name}_{abs(hash((full_name, make_hashable(task_args), make_hashable(kwargs))))}"
        ctx = await WorkflowExecutionContext.get()
        finished = [e for e in ctx.events if e.source_id == task_id and e.type in (ExecutionEventType.TASK_COMPLETED,
                                                                                   ExecutionEventType.TASK_FAILED)]
        if len(finished) > 0:
            return finished[0].value
        if not ctx.resumed:
            ctx.events.append(ExecutionEvent(type=ExecutionEventType.TASK_STARTED, source_id=task_id, name=full_name,
                                             value=task_args))

        try:
            output = None
            if self.cache:
                cache_manager = CacheManager.default()
                output = cache_manager.get(task_id, version=self.cache_version)
            if not output:
                scheduler = Scheduler()
                task_info = TaskInfo(
                    task_id=task_id,
                    task=self._func,
                    args=args,
                    kwargs=kwargs,
                    priority=self.priority,
                    deadline=self.deadline,
                    resource_requirements=self.resource_requirements,
                    schedule=self.schedule,
                    event_trigger=self.event_trigger
                )
                if self.event_trigger and self.event_trigger.get("type") in ["kubernetes", "airflow"]:
                    scheduler.register_kubernetes_trigger(task_info, self.event_trigger) if self.event_trigger[
                                                                                                "type"] == "kubernetes" else scheduler.register_airflow_trigger(
                        task_info, self.event_trigger)
                else:
                    await scheduler.schedule_task(task_info)
                if not self.schedule and not (
                        self.event_trigger and self.event_trigger.get("type") in ["http", "kubernetes", "airflow"]):
                    task_info = await scheduler.get_next_task()
                    if not task_info:
                        raise ExecutionError("No task available for execution")
                    executor = get_executor()
                    try:
                        if self.secret_requests:
                            secrets = SecretManager.current().get(self.secret_requests)
                            kwargs = {**kwargs, "secrets": secrets}
                        if self.metadata:
                            kwargs = {**kwargs, "metadata": TaskMetadata(task_id, full_name)}

                        # Retry logic
                        config = Configuration.get().settings.executor
                        retry_attempts = config.retry_attempts
                        retry_delay = config.retry_delay
                        retry_backoff = config.retry_backoff

                        for attempt in range(retry_attempts):
                            try:
                                if self.timeout > 0:
                                    output = await asyncio.wait_for(
                                        executor.execute(self._func, *args, **kwargs),
                                        timeout=self.timeout
                                    )
                                else:
                                    output = await executor.execute(self._func, *args, **kwargs)
                                break  # Success, exit the loop
                            except Exception as ex:
                                if attempt < retry_attempts - 1:
                                    wait_time = retry_delay * (retry_backoff ** attempt)
                                    ctx.events.append(
                                        ExecutionEvent(
                                            type=ExecutionEventType.TASK_RETRY_STARTED,
                                            source_id=task_id,
                                            name=full_name,
                                            value={"attempt": attempt + 1, "wait_time": wait_time}
                                        )
                                    )
                                    await asyncio.sleep(wait_time)
                                else:
                                    # All retries failed, attempt rollback and fallback
                                    if self.rollback:
                                        await maybe_awaitable(self.rollback)(*args, **kwargs)
                                    if self.fallback:
                                        output = await maybe_awaitable(self.fallback)(*args, **kwargs)
                                        ctx.events.append(
                                            ExecutionEvent(
                                                type=ExecutionEventType.TASK_FALLBACK_COMPLETED,
                                                source_id=task_id,
                                                name=full_name,
                                                value=output
                                            )
                                        )
                                        break
                                    # Log detailed error
                                    error_details = {
                                        "exception": str(ex),
                                        "task_args": task_args,
                                        "kwargs": kwargs
                                    }
                                    ctx.events.append(
                                        ExecutionEvent(
                                            type=ExecutionEventType.TASK_FAILED,
                                            source_id=task_id,
                                            name=full_name,
                                            value=error_details
                                        )
                                    )
                                    raise  # No fallback, raise the exception
                        if self.cache and output is not None:
                            cache_manager = CacheManager.default()
                            cache_manager.set(task_id, output, ttl=self.cache_ttl, version=self.cache_version)
                    finally:
                        executor.shutdown()
                        scheduler.release_resources(self.resource_requirements or {})
                else:
                    output = None
        except Exception as ex:
            error_details = {
                "exception": str(ex),
                "task_args": task_args,
                "kwargs": kwargs
            }
            ctx.events.append(
                ExecutionEvent(
                    type=ExecutionEventType.TASK_FAILED,
                    source_id=task_id,
                    name=full_name,
                    value=error_details
                )
            )
            raise

        if output is not None:
            ctx.events.append(
                ExecutionEvent(
                    type=ExecutionEventType.TASK_COMPLETED,
                    source_id=task_id,
                    name=full_name,
                    value=self.output_storage.store(task_id, output) if self.output_storage else output,
                )
            )
        ContextManager.default().save(ctx)
        return output
