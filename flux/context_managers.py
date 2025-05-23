from __future__ import annotations

from abc import ABC
from abc import abstractmethod

from sqlalchemy.exc import IntegrityError

from flux import Configuration
from flux.cache import CacheManager
from flux.context import WorkflowExecutionContext
from flux.errors import ExecutionContextNotFoundError
from flux.models import ExecutionEventModel
from flux.models import SQLiteRepository
from flux.models import WorkflowExecutionContextModel
from flux.monitoring import Monitoring


class ContextManager(ABC):
    @abstractmethod
    def save(self, ctx: WorkflowExecutionContext):  # pragma: no cover
        raise NotImplementedError()

    @abstractmethod
    def get(self, execution_id: str | None) -> WorkflowExecutionContext:  # pragma: no cover
        raise NotImplementedError()

    @staticmethod
    def default() -> ContextManager:
        return SQLiteContextManager()


class SQLiteContextManager(ContextManager, SQLiteRepository):
    def save(self, ctx: WorkflowExecutionContext):
        with self.session() as session:
            try:
                context = session.get(WorkflowExecutionContextModel, ctx.execution_id)
                if context:
                    context.output = ctx.output
                    additional_events = self._get_additional_events(ctx, context)
                    session.bulk_save_objects(additional_events)  # Bulk insert events
                else:
                    session.add(WorkflowExecutionContextModel.from_plain(ctx))
                session.commit()
                cache_manager = CacheManager.default()
                cache_manager.set(f"context_{ctx.execution_id}", ctx,
                                  ttl=Configuration.get().settings.cache.default_ttl, tags={f"workflow:{ctx.name}"})
                Monitoring.default().track_execution(ctx)
            except IntegrityError:
                session.rollback()
                raise

    def get(self, execution_id: str | None) -> WorkflowExecutionContext:
        # Check cache first
        cache_manager = CacheManager.default()
        ctx = cache_manager.get(f"context_{execution_id}")
        if ctx:
            return ctx
        with self.session() as session:
            context = session.get(WorkflowExecutionContextModel, execution_id)
            if context:
                return context.to_plain()
            raise ExecutionContextNotFoundError(execution_id)

    def _get_additional_events(self, ctx, context):
        existing_events = [(e.event_id, e.type) for e in context.events]
        return [
            ExecutionEventModel.from_plain(ctx.execution_id, e)
            for e in ctx.events
            if (e.id, e.type) not in existing_events
        ]
