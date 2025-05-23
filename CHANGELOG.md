# Changelog

All notable changes to Flux will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Support for serverless execution with AWS Lambda and Google Cloud Functions (`executors.py`).

## [0.2.3] - 2025-05-23
### Added
- Initial release with stateful workflows, task management, and API server.
- Distributed execution with RabbitMQ (`executors.py`).
- Caching with `CacheManager` (`cache.py`).

## [0.2.2] - 2025-04-15
### Fixed
- Bug in `WorkflowExecutionContext` state persistence (`context.py`).
