# Contributing to Flux

Flux is a community-driven, open-source project for distributed workflow orchestration, licensed under the Apache License 2.0. We welcome contributions from everyone! Whether you're fixing a bug, adding a feature, improving documentation, or suggesting ideas, your efforts help make Flux better.

## Getting Started

1. **Read the Overview**: Check out the [README.md](README.md) for a project overview, installation instructions, and quick start guide.
2. **Explore the Documentation**: Full documentation is available at [https://edurdias.github.io/flux](https://edurdias.github.io/flux/). Learn about core concepts, advanced features, deployment options, and more.
3. **Understand the License**: Flux is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details and third-party attributions.

## Community Guidelines
We are committed to fostering an inclusive and respectful community. Please adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions.

## How to Contribute

### 1. Fork and Clone the Repository
- Fork the repository on GitHub: [edurdias/flux](https://github.com/edurdias/flux).
- Clone your fork:
  ```bash
  git clone https://github.com/<your-username>/flux
  cd flux
  ```

### 2. Set Up Your Environment
- Install dependencies using Poetry:
  ```bash
  pip install poetry
  poetry install
  ```
- Set up pre-commit hooks for code quality:
  ```bash
  pre-commit install
  ```

### 3. Make Changes
- Create a branch for your changes:
  ```bash
  git checkout -b feature/your-feature
  ```
- Make your changes in the appropriate directory:
  - Code: `flux/` (e.g., `api.py`, `cache.py`)
  - Tests: `tests/` (e.g., `test_workflow.py`)
  - Documentation: `docs/` (e.g., `examples/`, `api/`)
  - Scripts: `scripts/` (e.g., `ci.py`)

### 4. Test Your Changes
- Run tests to ensure functionality:
  ```bash
  poetry run pytest --cov=flux
  ```
- Test CI workflows locally using `poe` tasks:
  ```bash
  poetry run poe test-pr --dryrun
  ```
  See `pyproject.toml` for available tasks (`test-pr`, `test-build`, `test-docs`).

### 5. Update Documentation
- Add or update documentation in `docs/` (e.g., new examples in `examples/`, API docs in `api/`).
- Use snippets from `docs/snippets/` for consistency (e.g., `installation.md`).
- Test documentation locally:
  ```bash
  mkdocs serve
  ```

### 6. Update the NOTICE File
For significant contributions (e.g., new features, major bug fixes), add your name or organization to the [NOTICE](NOTICE) file under "Contributor Attributions":
```
- Jane Doe: Implemented serverless executor support
```
The `check-notice` pre-commit hook will validate the `NOTICE` file.

### 7. Commit and Sign Off
- Commit your changes with a clear message, signing off to agree to the Developer Certificate of Origin (DCO):
  ```bash
  git commit -m "Add serverless executor support" -s
  ```
  Your commit message should include `Signed-off-by: Your Name <email>` (e.g., `Signed-off-by: Jane Doe <jane@example.com>`).

### 8. Push and Submit a Pull Request
- Push your branch:
  ```bash
  git push origin feature/your-feature
  ```
- Open a pull request (PR) using the [PR template](.github/PULL_REQUEST_TEMPLATE.md). Link to any related issues and describe your changes.

## Contribution Types

### Code Contributions
- Follow code style guidelines enforced by Ruff and MyPy (see `.pre-commit-config.yaml`).
- Add tests in `tests/` to cover new functionality.
- Update `CHANGELOG.md` with your changes under the `[Unreleased]` section.

### Documentation Contributions
- Add or improve content in `docs/` (e.g., new examples, API docs).
- Use snippets from `docs/snippets/` for consistency.
- Test locally with `mkdocs serve` to ensure rendering.

### Bug Reports and Feature Requests
- Use our [issue templates](.github/ISSUE_TEMPLATE/) to report bugs or suggest features.
- Provide detailed descriptions, steps to reproduce, and expected behavior.

## Dependency Management
Flux includes a `poetry.lock` file for reproducible builds. To manage dependencies:
- Add runtime dependencies to `[tool.poetry.dependencies]` in `pyproject.toml`.
- Add development dependencies to `[tool.poetry.group.dev.dependencies]`.
- Run `poetry lock --no-update` and `poetry install` after updates.
If using Flux as a library and encountering conflicts, regenerate the lock file:
```bash
poetry lock --no-update
poetry install
```

## Testing CI Workflows
Test CI workflows locally using `poe` tasks:
```bash
poetry run poe test-pr --dryrun
```
See `pyproject.toml` for available tasks and `scripts/ci.py` for implementation.

## Security Contributions
If you find a security vulnerability, follow our [Security Policy](SECURITY.md) to report it responsibly.

## Community
Join the conversation:
- **GitHub Discussions**: [edurdias/flux/discussions](https://github.com/edurdias/flux/discussions)
- **X**: Follow `@FluxProject` (replace with actual handle)

Thank you for contributing to Flux! 🚀