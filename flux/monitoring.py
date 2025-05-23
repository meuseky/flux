from prometheus_client import Counter, Gauge, Histogram, start_http_server
from flux.context import WorkflowExecutionContext
from flux.events import ExecutionEventType
import logging

logger = logging.getLogger("flux.monitoring")

class Monitoring:
    def __init__(self):
        self.workflow_executions = Counter(
            "flux_workflow_executions_total",
            "Total number of workflow executions",
            ["workflow_name", "status"]
        )
        self.task_executions = Counter(
            "flux_task_executions_total",
            "Total number of task executions",
            ["task_name", "status"]
        )
        self.execution_duration = Histogram(
            "flux_execution_duration_seconds",
            "Execution duration of workflows and tasks",
            ["name", "type"]
        )
        self.resource_usage = Gauge(
            "flux_resource_usage",
            "Current resource usage",
            ["resource_type"]
        )
        self.start_prometheus_server()

    def start_prometheus_server(self):
        port = Configuration.get().settings.monitoring.get("prometheus_port", 9090)
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")

    def track_execution(self, ctx: WorkflowExecutionContext):
        for event in ctx.events:
            if event.type == ExecutionEventType.WORKFLOW_COMPLETED:
                self.workflow_executions.labels(
                    workflow_name=ctx.name, status="completed"
                ).inc()
                self.execution_duration.labels(
                    name=ctx.name, type="workflow"
                ).observe(event.time.timestamp() - ctx.events[0].time.timestamp())
            elif event.type == ExecutionEventType.WORKFLOW_FAILED:
                self.workflow_executions.labels(
                    workflow_name=ctx.name, status="failed"
                ).inc()
            elif event.type == ExecutionEventType.TASK_COMPLETED:
                self.task_executions.labels(
                    task_name=event.name, status="completed"
                ).inc()
                self.execution_duration.labels(
                    name=event.name, type="task"
                ).observe(event.time.timestamp() - ctx.events[0].time.timestamp())
            elif event.type == ExecutionEventType.TASK_FAILED:
                self.task_executions.labels(
                    task_name=event.name, status="failed"
                ).inc()

    def update_resource_usage(self, resource_type: str, value: float):
        self.resource_usage.labels(resource_type=resource_type).set(value)

    @staticmethod
    def default() -> Monitoring:
        return Monitoring()
