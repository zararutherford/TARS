---
paths:
  - "engine/**"
---
# Engine rules (Python)
- uv only: `uv add`, `uv run`, `uv sync`. Never pip. `requires-python = ">=3.12,<3.13"`.
- Migrations are numbered plain SQL files in `src/tars/store/migrations/`. No ORM, no query builders.
- `store/db.py` is the single connection factory. It sets WAL mode and the SQLCipher key (from `keyring`, service `com.zararutherford.tars`, account `db-key`). Nothing else calls `sqlite3.connect`.
- Mail: open the Envelope Index read-only, never with `immutable=1` (WAL visibility). Bodies come from `.emlx` files.
- Messages: `chat.db` bodies are `attributedBody` typedstream blobs. Decode through `messages/typedstream_decode.py` with golden-blob tests.
- The decision layer has one entry point, `Cascade.decide(state, question)`. Tiers return `{"noul": p}`, `{"choice", ...}`, or `{"score", ...}`.
- Every write to the outside world goes through `actions/runner.py` with a token; executors never act on their own.
- Tests: `pytest` with synthetic Envelope Index, `.emlx` trees, and `chat.db` from `tests/fixtures/make_fake_*.py`. Mark anything that loads a model `@pytest.mark.needs_models`.
- No hosted AI hosts or SDKs (openai, anthropic, google-generativeai, cohere, mistralai, litellm, langchain*). Local inference only.
