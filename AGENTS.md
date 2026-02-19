# Repository Guidelines

## Project Structure & Module Organization
- Source: `polychat/` contains the FastAPI app, DI container, controllers per provider (`perplexity`, `gpt`, `kimi`, `deepseek`), service layer, and clients.
- Entrypoints: `polychat/api.py` (FastAPI), `polychat/cli.py` (CLI). Docker entrypoint runs `python -m polychat.api`.
- Tests: `tests/unit/` for isolated logic, `tests/integration/` for FastAPI `TestClient` flows, shared fakes in `tests/fakes.py`.
- Docs/config: `WORKSPACE.md`, `pir.json`, `requirements.txt`, `requirements-dev.txt`, `docker-compose.yml`.

## Build, Test, and Development Commands
- Run API locally: `python -m polychat.api` (env vars from `.env`; defaults host 0.0.0.0 port 8459).
- CLI login (Perplexity): `python -m polychat.cli perplexity:login`.
- Tests (after `pip install -r requirements.txt -r requirements-dev.txt`): `pytest`.
- Docker build/run: `docker compose up --build` (uses `Dockerfile`, maps `./var` for session storage).

## Coding Style & Naming Conventions
- Language: Python 3.11. Prefer type hints and Pydantic models for request/response schemas.
- Style: 4-space indent, snake_case for functions/vars, PascalCase for classes.
- Keep coherence between module names and classes (e.g., `abstract_client.py` -> `AbstractClient`), and place shared helpers in the client package rather than scattering new files.
- Client helpers should centralize cross-cutting concerns (es. retry policy, input mode) in the base client and reuse from specific providers; avoid duplicare logica o introdurre modelli non documentati.
- Controllers are provider-scoped (e.g., `PerplexityChatController`) with routers mounted under `/<provider>/chats`.
- Keep modules small: avoid mixing unrelated classes/functions in the same file; split fakes/builders/fixtures across separate modules.
- Keep all `__init__.py` files empty; do not use them for re-exports.
- Keep comments minimal and purposeful; avoid non-ASCII unless required.

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio` for async, FastAPI `TestClient`/`httpx` for routes.
- Naming: `tests/unit/.../test_*.py`, `tests/integration/test_*.py`; use fakes over network/browser calls.
- Aim for deterministic tests; avoid hitting real Perplexity/browser in CI by stubbing clients.

## Commit & Pull Request Guidelines
- Commits: concise, imperative summaries (e.g., “Add GPT controller placeholder”). Group related changes.
- PRs: describe scope, key changes, and testing done (`pytest`, manual, or not run). Link issues/cards when applicable; include screenshots/logs for UI or API changes if helpful.
