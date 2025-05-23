from __future__ import annotations
from flux import task, workflow, WorkflowExecutionContext
from flux.tasks import parallel


@task
async def say_hi(name: str):
    return f"Hi, {name}"


@task
async def say_hello(name: str):
    return f"Hello, {name}"


@task
async def diga_ola(name: str):
    return f"Ola, {name}"


@task
async def saluda(name: str):
    return f"Hola, {name}"


@workflow
async def parallel_tasks_workflow(ctx: WorkflowExecutionContext[str]):
    results = await parallel(
        say_hi(ctx.input),
        say_hello(ctx.input),
        diga_ola(ctx.input),
        saluda(ctx.input),
    )
    return results


if __name__ == "__main__":
    # Run with local execution
    ctx = parallel_tasks_workflow.run("Joe")
    print(ctx.to_json())

    # Run with distributed execution
    from flux.config import Configuration

    Configuration().override(executor={"execution_mode": "distributed"})
    ctx = parallel_tasks_workflow.run("Joe")
    print(ctx.to_json())
