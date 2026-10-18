# TARS

Personal, local-only macOS assistant for one user. It reads Apple Mail and iMessage, proposes
actions, and learns from outcomes. Nothing leaves the machine.

- Plan: `docs/technical-plan.md` (snapshot of the living Claude Doc linked in `CLAUDE.md`).
- Engine: `engine/` (Python 3.12, uv). App: `swift/` (SwiftPM, `TARS.app`).
- Entry points: `make setup | build | run | check | models`.

## First run

```sh
make setup      # uv sync, pre-commit hook, seed ~/Library/Application Support/TARS/tars.toml
make check      # ruff, mypy, pytest, swift build, swift test, no-AI-endpoint check
make build      # dist/TARS.app, signed with the self-signed "TARS Dev" identity
make run
```

The first `make build` creates the "TARS Dev" code-signing identity in your login keychain and
may show a Keychain prompt once. Never sign ad-hoc; TCC grants are keyed on the stable identity
and the bundle id `com.zararutherford.tars`.

## Rules

- Local inference only. `scripts/check_no_ai_endpoints.sh` runs as a hook, in pre-commit and in CI.
- Real Mail and Messages data stay on this machine and out of fixtures, docs and commits.
- Plain SQL migrations, no ORM. Swift holds no business logic.
