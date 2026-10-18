# TARS

Personal, local-only macOS assistant for one user. It reads Apple Mail and iMessage, proposes actions, and learns from outcomes. Nothing leaves the machine.

## Canonical plan
- The technical plan is a living Claude Doc: https://claude.ai/code/artifact/67cf3736-e708-48c5-ac01-78e99256ef77 (read it with the Docs tools, not web fetch).
- `docs/technical-plan.md` is the snapshot taken at each milestone boundary. Build one milestone at a time; each has a "Done when" row.
- Target machine: M1 Pro, 16 GB, macOS 26. Size models and memory for 16 GB.

## Layout
- `engine/` Python 3.12 via uv. Everything that thinks. Scripts: `tars`, `tars-daemon`, `tars-llm`, `tars-nightly`.
- `swift/` SwiftPM package. `TARS.app` (LSUIElement) is a pure socket client and the parent of the daemon so TCC grants are inherited.
- `scripts/` bundle, sign, launchagent, model download, `check_no_ai_endpoints.sh`.
- `docs/` spec PDF, plan snapshot, PERMISSIONS.md, QUESTIONS.md, `adr/`.

## Commands
- `make setup | build | run | check | models` are the entry points. `make check` = ruff, mypy, pytest (not `needs_models`), swift build, endpoint check.
- Python: `cd engine && uv run pytest`, `uv run ruff check`, `uv run mypy`. Tests that load Qwen carry the `needs_models` marker and are excluded by default.
- Swift: `cd swift && swift build`, `swift test`.

## Hard rules
- Real data is in scope during development. The user has authorized reading `~/Library/Mail`, `~/Library/Messages/chat.db`, and `~/Library/Application Support/TARS` directly (sqlite3, the `tars` CLI, scripts) to inspect schemas, debug parsers, and dogfood. Use it whenever it makes the work better.
- What stays out: never commit real messages, addresses, or bodies; never copy them into `engine/tests/fixtures/`, docs, ADRs, or commit messages. Tests run on synthetic fixtures so they are deterministic and safe in CI. If a real case is needed as a regression test, anonymize it first.
- No hosted AI endpoints or SDKs anywhere in the code or lockfile. `scripts/check_no_ai_endpoints.sh` enforces this in a hook, pre-commit, and CI. Inference is local (mlx_lm in-process, or an OpenAI-compatible local server).
- Plain SQL migrations, no ORM. `store/db.py` is the only place that opens the database.
- Swift holds no business logic. Decisions, state, and scheduling live in the Python engine.
- Do not commit unless asked. Conventional commits, no Co-Authored-By.

## Style
- Python: ruff + mypy strict, explicit return types on every function, early returns over nesting, `structlog` for logs.
- Swift: Swift 6 strict concurrency, explicit types at API boundaries.
- Ask before implementing when two approaches are genuinely open.
