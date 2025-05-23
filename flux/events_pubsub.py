from google.cloud import pubsub_v1
from flux.scheduler import Scheduler, TaskInfo
from flux.context import WorkflowExecutionContext
from flux.events import ExecutionEvent, ExecutionEventType
import logging

logger = logging.getLogger("flux.events_pubsub")

class PubSubTrigger:
    def __init__(self, project_id: str, subscription_name: str):
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(project_id, subscription_name)
        self.scheduler = Scheduler()

    def start(self, task_info: TaskInfo):
        def callback(message: pubsub_v1.subscriber.message.Message):
            ctx = WorkflowExecutionContext.get()
            logger.info(f"Received Pub/Sub message for task {task_info.task_id}")
            ctx.events.append(ExecutionEvent(
                type=ExecutionEventType.TASK_TRIGGERED,
                source_id=task_info.task_id,
                name="pubsub_trigger",
                value=message.data.decode("utf-8")
            ))
            self.scheduler._enqueue_task(task_info)
            message.ack()

        self.subscriber.subscribe(self.subscription_path, callback=callback)
        logger.info(f"Started Pub/Sub subscription for task {task_info.task_id}")

    def stop(self):
        self.subscriber.close()
