from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
import asyncio
import heapq
import logging

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from flux import Monitoring
from flux.config import Configuration
from flux.context import WorkflowExecutionContext
from flux.events import ExecutionEvent, ExecutionEventType
from fastapi import FastAPI, Request, HTTPException

from flux.events_pubsub import PubSubTrigger

logger = logging.getLogger("flux.scheduler")

@dataclass
class TaskInfo:
    task_id: str
    task: Callable[..., Any]
    args: tuple
    kwargs: dict
    priority: int  # Lower number = higher priority
    deadline: Optional[datetime] = None
    resource_requirements: Dict[str, Any] = None
    schedule: Optional[str] = None  # Cron expression
    event_trigger: Optional[Dict[str, str]] = None  # e.g., {"type": "file", "path": "/path"} or {"type": "http", "endpoint": "/webhook"}

    def __lt__(self, other):
        self_score = (self.priority, self.deadline or datetime.max)
        other_score = (other.priority, other.deadline or datetime.max)
        return self_score < other_score

class ResourceManager:
    def __init__(self):
        config = Configuration.get().settings.executor
        self.resources = {
            "cpu": config.available_cpu,
            "memory": config.available_memory * 1024,  # Convert GB to MB
            "gpu": config.available_gpu
        }
        self.allocated = {"cpu": 0, "memory": 0, "gpu": 0}

    def can_allocate(self, requirements: Dict[str, Any]) -> bool:
        required_cpu = requirements.get("cpu", 0)
        required_memory = requirements.get("memory", 0) * 1024  # Convert GB to MB
        required_gpu = requirements.get("gpu", 0)
        return (
            self.resources["cpu"] - self.allocated["cpu"] >= required_cpu and
            self.resources["memory"] - self.allocated["memory"] >= required_memory and
            self.resources["gpu"] - self.allocated["gpu"] >= required_gpu
        )

    def allocate(self, requirements: Dict[str, Any]):
        self.allocated["cpu"] += requirements.get("cpu", 0)
        self.allocated["memory"] += requirements.get("memory", 0) * 1024
        self.allocated["gpu"] += requirements.get("gpu", 0)
        Monitoring.default().update_resource_usage("cpu", self.allocated["cpu"])
        Monitoring.default().update_resource_usage("memory", self.allocated["memory"])
        Monitoring.default().update_resource_usage("gpu", self.allocated["gpu"])
        logger.info(f"Allocated resources: {requirements}")

    def release(self, requirements: Dict[str, Any]):
        self.allocated["cpu"] = max(0, self.allocated["cpu"] - requirements.get("cpu", 0))
        self.allocated["memory"] = max(0, self.allocated["memory"] - (requirements.get("memory", 0) * 1024))
        self.allocated["gpu"] = max(0, self.allocated["gpu"] - requirements.get("gpu", 0))
        Monitoring.default().update_resource_usage("cpu", self.allocated["cpu"])
        Monitoring.default().update_resource_usage("memory", self.allocated["memory"])
        Monitoring.default().update_resource_usage("gpu", self.allocated["gpu"])
        logger.info(f"Released resources: {requirements}")

class Scheduler:
    def __init__(self):
        self.task_queue: List[TaskInfo] = []
        self.resource_manager = ResourceManager()
        self.scheduler = AsyncIOScheduler()
        self.event_observer = Observer()
        self.running = False
        self.fastapi_app = FastAPI()
        self._setup_webhooks()
        self.scheduler.start()
        self._setup_ci_cd_triggers()

    def _setup_webhooks(self):
        @self.fastapi_app.post("/webhook/{task_id}")
        async def handle_webhook(task_id: str, request: Request):
            ctx = await WorkflowExecutionContext.get()
            task_info = next((t for t in self.task_queue if t.task_id == task_id), None)
            if task_info:
                logger.info(f"HTTP trigger for task {task_id}")
                ctx.events.append(ExecutionEvent(
                    type=ExecutionEventType.TASK_TRIGGERED,
                    source_id=task_id,
                    name="http_trigger",
                    value={"endpoint": f"/webhook/{task_id}", "payload": await request.json()}
                ))
                self._enqueue_task(task_info)
            return {"status": "received"}

        @self.fastapi_app.post("/ci-cd/{task_id}")
        async def handle_ci_cd_trigger(task_id: str, request: Request):
            payload = await request.json()
            ctx = await WorkflowExecutionContext.get()
            task_info = next((t for t in self.task_queue if t.task_id == task_id), None)
            if not task_info:
                raise HTTPException(status_code=404, detail="Task not found")
            source = payload.get("source", "unknown")
            if source == "github":
                if not payload.get("action") == "completed":
                    return {"status": "ignored"}
            elif source == "jenkins":
                if not payload.get("status") == "SUCCESS":
                    return {"status": "ignored"}
            logger.info(f"CI/CD trigger for task {task_id} from {source}")
            ctx.events.append(ExecutionEvent(
                type=ExecutionEventType.TASK_TRIGGERED,
                source_id=task_id,
                name=f"ci_cd_trigger_{source}",
                value=payload
            ))
            self._enqueue_task(task_info)
            return {"status": "received"}

    def _setup_ci_cd_triggers(self):
        @self.fastapi_app.post("/ci-cd/register/{task_id}")
        async def register_ci_cd_trigger(task_id: str, request: Request):
            config = await request.json()
            task_info = next((t for t in self.task_queue if t.task_id == task_id), None)
            if not task_info:
                raise HTTPException(status_code=404, detail="Task not found")
            if config.get("type") == "github":
                # Register webhook with GitHub
                github_repo = config.get("repo")
                webhook_url = f"{Configuration.get().settings.api_url}/ci-cd/{task_id}"
                headers = {"Authorization": f"Bearer {config.get('token')}"}
                payload = {
                    "name": "web",
                    "active": True,
                    "events": ["workflow_run"],
                    "config": {"url": webhook_url, "content_type": "json"}
                }
                response = requests.post(
                    f"https://api.github.com/repos/{github_repo}/hooks",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                logger.info(f"Registered GitHub webhook for task {task_id}")
            elif config.get("type") == "jenkins":
                # Register Jenkins webhook (simplified)
                logger.info(f"Registered Jenkins webhook for task {task_id}")
            return {"status": "registered"}

    def register_ci_cd_trigger(self, task_info: TaskInfo, config: Dict[str, Any]):
        trigger_type = config.get("type")
        if trigger_type in ["github", "jenkins"]:
            heapq.heappush(self.task_queue, task_info)
            logger.info(f"Registered {trigger_type} CI/CD trigger for task {task_info}")
        else:
            raise ValueError(f"Unsupported CI/CD trigger type: {trigger_type}")

    async def schedule_task(self, task_info: TaskInfo):
        try:
            if task_info.schedule:
                self.scheduler.add_job(
                    self._enqueue_task,
                    "cron",
                    args=[task_info],
                    **self._parse_cron(task_info.schedule)
                )
                logger.info(f"Scheduled cron task {task_info.task_id}: {task_info.schedule}")
            elif task_info.event_trigger:
                trigger_type = task_info.event_trigger.get("type")
                if trigger_type == "file":
                    self.register_file_trigger(task_info, task_info.event_trigger["path"])
                elif trigger_type == "http":
                    heapq.heappush(self.task_queue, task_info)  # HTTP tasks wait for webhook
                    logger.info(f"Registered HTTP trigger for task {task_info.task_id}")
                elif trigger_type == "pubsub":
                    pubsub_trigger = PubSubTrigger(
                        task_info.event_trigger["project_id"],
                        task_info.event_trigger["subscription_name"]
                    )
                    pubsub_trigger.start(task_info)
                    # TODO fetch task_id instead
                    logger.info(f"Registered Pub/Sub trigger for task {task_info}")
                else:
                    raise ValueError(f"Unsupported event trigger type: {trigger_type}")
            else:
                heapq.heappush(self.task_queue, task_info)
                logger.info(f"Enqueued task {task_info.task_id}")
        except Exception as e:
            logger.error(f"Failed to schedule task {task_info.task_id}: {str(e)}")
            ctx = await WorkflowExecutionContext.get()
            ctx.events.append(ExecutionEvent(
                type=ExecutionEventType.TASK_FAILED,
                source_id=task_info.task_id,
                name="scheduler",
                value=str(e)
            ))
            raise

    def _parse_cron(self, cron: str) -> Dict[str, Any]:
        parts = cron.split()
        if len(parts) != 5:
            raise ValueError("Invalid cron expression")
        return {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "day_of_week": parts[4]
        }

    def _enqueue_task(self, task_info: TaskInfo):
        heapq.heappush(self.task_queue, task_info)
        logger.info(f"Enqueued task {task_info.task_id} via trigger")

    async def get_next_task(self) -> Optional[TaskInfo]:
        while self.task_queue and self.running:
            task_info = heapq.heappop(self.task_queue)
            if self.resource_manager.can_allocate(task_info.resource_requirements or {}):
                if task_info.deadline and task_info.deadline < datetime.now():
                    logger.warning(f"Task {task_info.task_id} missed deadline")
                    continue
                self.resource_manager.allocate(task_info.resource_requirements or {})
                return task_info
            heapq.heappush(self.task_queue, task_info)
            await asyncio.sleep(0.1)
        return None

    def release_resources(self, requirements: Dict[str, Any]):
        self.resource_manager.release(requirements or {})

    def register_file_trigger(self, task_info: TaskInfo, event_path: str):
        handler = FileEventHandler(task_info, self._enqueue_task)
        self.event_observer.schedule(handler, event_path, recursive=False)
        if not self.event_observer.is_alive():
            self.event_observer.start()
        logger.info(f"Registered file trigger for task {task_info.task_id} at {event_path}")

    def register_kubernetes_trigger(self, task_info: TaskInfo, config: Dict[str, Any]):
        # Placeholder for Kubernetes integration
        logger.info(f"Kubernetes trigger registered for task {task_info.task_id} (config: {config})")
        # Future: Use kubernetes-python to create a CronJob or watch events

    def register_airflow_trigger(self, task_info: TaskInfo, config: Dict[str, Any]):
        # Placeholder for Airflow integration
        logger.info(f"Airflow trigger registered for task {task_info.task_id} (config: {config})")
        # Future: Generate Airflow DAG or use Airflow API

    def start(self):
        self.running = True
        logger.info("Scheduler started")

    def shutdown(self):
        self.scheduler.shutdown()
        self.event_observer.stop()
        self.event_observer.join()
        self.running = False
        logger.info("Scheduler shutdown")

class FileEventHandler(FileSystemEventHandler):
    def __init__(self, task_info: TaskInfo, enqueue_callback: Callable[[TaskInfo], None]):
        self.task_info = task_info
        self.enqueue_callback = enqueue_callback

    def on_modified(self, event):
        if not event.is_directory:
            logger.info(f"File trigger for task {self.task_info.task_id}: {event.src_path}")
            self.enqueue_callback(self.task_info)

class LoadBalancer:
    def __init__(self):
        self.nodes = []  # List of (node_id, resource_manager)

    def register_node(self, node_id: str, resource_manager: ResourceManager):
        self.nodes.append((node_id, resource_manager))

    def select_node(self, task_info: TaskInfo) -> Optional[str]:
        for node_id, rm in self.nodes:
            if rm.can_allocate(task_info.resource_requirements or {}):
                return node_id
        return None
