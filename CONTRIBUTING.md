# Contributing to unified-ui Platform Service

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/unified-ui/unified-ui-platform-service.git
cd unified-ui-platform-service

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# Start infrastructure
docker compose -f docker/local/infra/docker-compose.yml up -d

# Run database migrations
alembic upgrade head

# Start the server
uv run uvicorn unifiedui.app:app --reload
```

## Development Workflow

1. **Fork** the repository
2. **Create a branch** following the naming convention: `<type>/<description>`
   - Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`
   - Example: `feat/add-chat-agent-cloning`
3. **Make your changes** and write tests
4. **Run quality checks** locally:
   ```bash
   ruff check .                             # Lint
   ruff format .                            # Format
   mypy unifiedui/                          # Type check
   pytest tests/ -n auto --no-header -q     # Tests (parallel)
   pre-commit run --all-files               # All pre-commit hooks
   ```
5. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat(handlers): add chat agent cloning endpoint
   fix(auth): handle expired refresh tokens
   ```
6. **Push** and open a Pull Request against `develop`

## Code Standards

- **Type hints** on all public functions and methods
- **Docstrings** in Google style on all public APIs
- **No inline comments** — code must be self-documenting
- **Test coverage** must stay above **80%**
- **Ruff** must pass with zero warnings
- **Files under 400 lines** — split large modules into helpers

## Pull Request Guidelines

- PRs to `main` must come from `develop` or `hotfix/*` branches
- PRs to `develop` must come from `feat/*`, `fix/*`, `docs/*`, `refactor/*`, or similar typed branches
- All CI checks must pass before merge
- Squash merge feature branches for a clean history

## Reporting Issues

- Use GitHub Issues
- Include: Python version, steps to reproduce, expected vs. actual behavior
- For security vulnerabilities, see [SECURITY.md](SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
