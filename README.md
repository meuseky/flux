<p align="center">
  <img src="docs/assets/logo.png" alt="Flux Logo" width="200"/>
</p>

<h1 align="center">Flux</h1>

<p align="center">
  A distributed workflow orchestration engine for building stateful, fault-tolerant workflows.
</p>

<p align="center">
  <a href="https://github.com/edurdias/flux/actions/workflows/pre-commit.yml">
    <img src="https://github.com/edurdias/flux/actions/workflows/pre-commit.yml/badge.svg" alt="CI Status"/>
  </a>
  <a href="https://pypi.org/project/flux-core/">
    <img src="https://img.shields.io/pypi/v/flux-core.svg" alt="PyPI Version"/>
  </a>
  <a href="https://github.com/edurdias/flux/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg" alt="Apache 2.0 License"/>
  </a>
</p>

Flux is a community-driven, open-source Python framework for creating reliable, distributed workflows. It offers stateful execution, robust error handling, and flexible deployment options (local, distributed, serverless), making it ideal for data pipelines, CI/CD, and enterprise applications.

## Key Features

- **Stateful Workflows**: Persist execution state and history with `WorkflowExecutionContext`.
- **Distributed Execution**: Run workflows locally, on Kubernetes, or serverless (AWS Lambda, Google Cloud Functions).
- **High Performance**: Leverage caching (`CacheManager`), parallel tasks, and RabbitMQ for scalability.
- **Type Safety**: Use Python type hints for safer development, validated by MyPy.
- **API-Driven**: Execute workflows via a FastAPI server with HTTP endpoints.
- **Flexible Patterns**: Support pipelines, parallel tasks, subworkflows, and DAGs.
- **Error Handling**: Automatic retries, fallbacks, rollbacks, and timeouts.
- **Plugins**: Extend functionality with Kubernetes, S3, and serverless plugins.

## Installation
Install Flux using pip:
```bash
pip install flux-core
```
Or use Docker:
```bash
docker pull flux:latest
docker run -p 8000:8000 flux:latest
```
Requirements: Python 3.12+, Poetry for dependency management.

## Quick Start
Create and run a simple workflow:
```python
from flux import task, workflow, WorkflowExecutionContext

@task
def say_hello(name: str) -> str:
    return f"Hello, {name}"

@workflow
def hello_world(ctx: WorkflowExecutionContext[str]):
    return say_hello(ctx.input)

# Execute locally
result = hello_world.run("World")
print(result.output)  # Outputs: Hello, World
```
Explore more examples in the documentation.

## Configuration
Customize Flux with flux.toml:
```toml
[flux]
database_url = "postgresql://user:pass@db:5432/flux"
cache.backend = "redis"
executor.execution_mode = "distributed"
```
See Configuration for details.

## Deployment
Deploy Flux with Docker, Kubernetes, or serverless platforms:
```bash
# Docker Compose with Redis and PostgreSQL
docker-compose -f docker-compose.yml up
```
See Deployment for Docker, Kubernetes, and serverless guides.

## Development
### Setup
```bash
git clone https://github.com/edurdias/flux
cd flux
poetry install
```
### Run Tests
```bash
poetry run pytest
```
### Code Quality
Flux uses:
- Ruff: Linting and formatting
- MyPy: Type checking
- Pytest: Testing
- Pre-commit: Code quality hooks

Run checks:
```bash
pre-commit run --all-files 
```

## Documentation
Full documentation is available at https://edurdias.github.io/flux. Explore installation, core concepts, advanced features, and deployment options.

## License
Flux is licensed under the Apache License 2.0, maintained by Flux Contributors. See the LICENSE and NOTICE files for details and third-party attributions.

## Security
For security vulnerabilities, please follow our [Security Policy](SECURITY.md).

## Contributing
Join our community! Open issues or submit pull requests using our [templates](https://github.com/edurdias/flux/tree/main/.github/ISSUE_TEMPLATE).

## Changelog
See [CHANGELOG.md](CHANGELOG.md) for a history of changes and updates.

## Community Standards
We are committed to fostering an inclusive community. Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

## Join the Community
- GitHub: edurdias/flux
- Discussions: Join our GitHub Discussions

Built with ❤️‍🔥 by Flux Contributors