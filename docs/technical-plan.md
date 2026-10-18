<!--
Snapshot of the living plan, taken at the M-1 boundary on 2026-10-17 (doc rev 18).
Source: https://claude.ai/code/artifact/67cf3736-e708-48c5-ac01-78e99256ef77
Edit the Claude Doc, not this file; re-export at each milestone boundary.
M-1 deviations from the doc: profile thresholds are small < 32 GB, medium < 64 GB, large >= 64 GB;
M-1 pins only the dependencies its code imports, later milestones add theirs;
`[paths] data_dir` is not a config key (the file lives inside it); TARS_DATA_DIR relocates the data dir.
-->

# TARS Technical Plan

Oct 17, 2026 · @Zara Rutherford

## Context

TARS is a personal assistant that runs entirely on the user's Mac, reads mail, texts, calendar, contacts, reminders and files, learns what matters from what the user does, and never lets data leave the machine. The build spec (Tars — Build Spec v0.1, 2026-10-17) fixes the non-negotiables: no third-party AI, read anything but write nothing without permission, drafts not sends, zero creator visibility, swappable brains. It also fixes a 9-component architecture, a three-tier classifier cascade, an implicit-signal learning loop, standing concerns, compute profiles, a security model, and a build order M0–M9.

This plan turns that spec into an executable engineering plan: repo layout, process topology, data model, interfaces, per-milestone work items, risks, and verification. Nothing exists yet; the first execution step is bootstrapping the repo. Every threshold here is a starting point to be tuned against real use, as the spec demands.

Decisions taken with the user on 2026-10-17:

- This document is the canonical, living plan. A snapshot is exported to `docs/technical-plan.md` when the repo is bootstrapped (M-1) and at each milestone.
- The planning session delivers the document only. Repo bootstrap and M0 start in a later session.
- M4 drafts land in Mail.app's Drafts folder (spec default). A `drafts.sink = "inbox"` option keeps drafts inside TARS for anyone who does not want them synced to their mail provider.

## Verified facts that shape the plan

Checked on the target machine on 2026-10-17. Six months of mail plus texts on this machine is about 55k events, which matches the spec's sizing.

| Fact | Consequence |
| --- | --- |
| The Mac is an M1 Pro, 16 GB, macOS 26.5.2, with Xcode and Swift 6.3 installed | It is the spec's "small" profile target. Build and dogfood here. |
| `uv`, `ollama` (no models), `git`, `gh`, `brew` present; system Python is 3.14; no ML libraries installed; no code-signing identities | Pin Python 3.12 via `uv` (MLX, torch, sentence-transformers and `jeff` all target it). Self-signed signing only; a Network Extension and notarized updates need an Apple Developer account, so they are M9 options, not dependencies. |
| Mail.app store is `~/Library/Mail/V10/MailData/Envelope Index` (WAL mode, about 52k messages, 6.4k in the last 6 months). The `messages` table carries sender, subject, dates, mailbox, `conversation_id`, `read`, `flagged`, `deleted`, `date_last_viewed`, `list_id_hash`, `automated_conversation`, `is_urgent`. Bodies are `.emlx` files under `<Mailbox>.mbox/*/Data/<reversed digits of ROWID div 1000>/Messages/<ROWID>.emlx`; `message_global_data.message_id_header` holds the RFC Message-ID. | Mail connector = Envelope Index for metadata plus `.emlx` parsing for bodies. `conversation_id` gives threads for free; the read/viewed/deleted/flagged columns give free implicit signals; the automated and list flags are free tier-0 and tier-1 features. |
| `~/Library/Messages/chat.db` (about 705 MB, 48k messages in 6 months). Nearly all rows have `text IS NULL` with the body in `attributedBody` (typedstream); `date` is nanoseconds since 2001-01-01; chat style 45 = one-to-one, 43 = group. | Messages connector needs typedstream decoding (the `typedstream` PyPI library plus a heuristic fallback). Terminal already has Full Disk Access. |
| Jev (TypeSafe, released 2026-09-15) wire format: `POST /v1/systemone` with `state` and a map of typed questions (noul, choice, score, each with instructions and criteria); answers are `{noul: p}`, `{choice, probabilities, confidence}`, `{score, probabilities, confidence, legend}`. Self-hosted clones exist: [jeff](https://github.com/logan-markewich/jeff) (GLiFormer 400M, uv + Python 3.12, MPS, serves on port 8000), [von](https://github.com/wfzyx/von), [firelex/jeff](https://github.com/firelex/jeff) (0.8B). | `decide()` adopts this exact shape, so a local jeff or von drops in with one config line. |
| [mlx-community/Qwen3-8B-4bit](https://huggingface.co/mlx-community/Qwen3-8B-4bit) exists; stock `mlx_lm.server` silently ignores `response_format`. Outlines supports the `mlx_lm` runtime. Qwen3.5-4B-MLX-8bit (about 4.8 GB) is a newer small alternative. | Tier 2 runs `mlx_lm` in-process inside a TARS-owned server; typed answers come from logits over the allowed options, not from a grammar library. The model name is a config value. |
| `sqlcipher3` ships cp312 macOS arm64 wheels. | Encryption at rest is cheap to enable early. |
| Mail.app AppleScript: `make new outgoing message` followed by `save` lands the message in Drafts; `reply` preserves threading headers. | The M4 draft sink is viable; verify on macOS 26 as the first M4 task. |

## Architecture

TARS is one Swift app that owns every macOS permission, with a Python daemon underneath doing all the thinking. The daemon hosts a single Unix socket; every other process is its child or its client, and the only door to the outside world is the actions module.

[diagram in the living doc: component map · nine components, one write path]

Senses feed one encrypted store, the cascade scores every event, proposals wait for the user, actions are the only door out, and the learning loop feeds every outcome back into rules and heads.

### Processes and supervision

[diagram in the living doc: process topology · one app, one daemon, four children]

launchd keeps TARS.app alive; the app spawns the daemon so it inherits every permission grant, and the daemon spawns and supervises everything else.

| Process | Language | Role | Lifecycle |
| --- | --- | --- | --- |
| `TARS.app` | Swift, LSUIElement bundle | The single TCC principal: EventKit, Contacts, UNUserNotificationCenter, NSAppleScript, menu-bar UI (M6). Pure client of the daemon. | launchd LaunchAgent (KeepAlive, RunAtLoad) from M3; before that `tars daemon run` in Terminal |
| `tars-daemon` | Python | Watchers every 60 s, cascade, proposals, scheduler, Unix-socket API | Spawned and restarted with backoff by `Supervisor.swift` |
| `tars-llm` | Python | `mlx_lm` in-process; loads Qwen on demand, unloads after idle to free about 5 GB | Spawned and restarted by `daemon/supervisor.py` |
| `tars-nightly` | Python | The learning loop's nightly job | Spawned by the daemon on schedule; separate process so training memory is freed |
| `mitmdump` with the egress addon | Python | Read-only internet gate for browser actions | M7, only while a browser action is pending |
| Chromium via Playwright |  | Browser agent | M7, proxied through mitmdump |
| `tars` CLI | Python (typer) | `tars events`, `decide`, `backfill`, `nightly`, `proposals`, `models`, `doctor` | On demand, over the daemon socket |

The app is the daemon's parent because macOS TCC attributes a child process to its responsible process. If the daemon were its own LaunchAgent, the user would have to grant Full Disk Access to the venv's Python binary, which is broad and breaks whenever `uv sync` replaces the binary. With `TARS.app` as the parent, one grant covers the daemon, exactly as Terminal's grant covered the read-only checks that produced the verified facts above. AppleScript runs inside the Swift process so the "TARS wants to control Mail" prompt is attributed to the app.

launchd knows only `TARS.app`. The nightly job is scheduled inside the daemon: at 03:00, or on catch-up when the last success is older than 20 h, it checks AC power (`pmset -g batt`) and idle time (`ioreg -c IOHIDSystem` HIDIdleTime over 5 min), then spawns `tars-nightly`; otherwise it retries every 30 min.

### IPC

One Unix domain socket hosted by the daemon at `~/Library/Application Support/TARS/run/daemon.sock`, mode 0600. Filesystem permissions are the auth. No listening port exists, so a malicious web page cannot `fetch()` the API, and a Little Snitch rule can deny the daemon all network access outright.

- CLI to daemon: HTTP/1.1 + JSON over the socket (`httpx.HTTPTransport(uds=...)`, uvicorn `--uds`).
- TARS.app to daemon: newline-delimited JSON over the same socket via `Network.framework` (`NWConnection` + `NWEndpoint.unix`), so the Swift side needs no HTTP library. Daemon-to-app commands are `{id, kind, args}` (`notify.post`, `calendar.query`, `calendar.create`, `reminders.query`, `reminders.create`, `contacts.dump`, `applescript.run`, `permissions.status`, `permissions.request`); app-to-daemon events are `notification.action`, `eventstore.changed`, `contacts.changed`, `chat.message`, plus command results.
- Daemon to `tars-llm`: a second socket `run/llm.sock` exposing `/health`, `/v1/chat/completions` (streaming), `/v1/slots`, `/v1/extract`, `/v1/unload`.

### Signing

Use a self-signed code-signing identity ("TARS Dev", created once by `scripts/dev_sign.sh`), not ad-hoc `codesign -s -`. Ad-hoc signatures change on every build, and TCC treats each build as a new app, re-prompting for Calendar, Contacts and Automation. Pick the bundle id once (`com.zararutherford.tars`) and never change it; TCC grants are keyed on it. Developer ID signing only at M9.

### Repo layout

A monorepo, `git init` in the project folder.

```text
TARS/
  README.md, Makefile (setup | build | run | check | models)
  tars.toml.example              copied to ~/Library/Application Support/TARS/tars.toml
  .github/workflows/ci.yml       ruff, mypy, pytest -m "not needs_models", swift build, no-AI-endpoint check
  .pre-commit-config.yaml        same endpoint check locally
  engine/                        Python: everything that thinks
    pyproject.toml               package "tars", requires-python >=3.12,<3.13; scripts tars, tars-daemon, tars-llm, tars-nightly
    .python-version, uv.lock
    src/tars/
      cli.py, config.py, paths.py, log.py, audit.py
      store/      db.py (connection factory, SQLCipher flag), keychain.py, migrations/*.sql, repos/, vectors.py
      senses/     base.py, watcher.py, normalize.py, mail/{envelope,emlx,quotes,html}.py, messages/{chatdb,typedstream_decode}.py, eventkit/, documents.py
      people/     resolve.py, stats.py, fingerprints.py
      brain/      types.py, questions.py, cascade.py, rules/{dsl,engine,render}.py, tier1/{features,heads,train,calibrate}.py, tier2/{prompt,slots,extract,client}.py, examples.py
      llm/        server.py (tars-llm), backends/{mlx_inproc,openai_compat}.py
      embed/      base.py, sentence_transformers_backend.py
      proposals/  engine.py, states.py, notify.py, shadow.py
      actions/    runner.py, tokens.py, permissions.py, executors/{mail_draft,reminder,calendar,browser}.py, recipes/
      egress/     mitm_addon.py, leakset.py
      drafts/, commitments/, concerns/, phone/
      learning/   nightly.py, harvest_*.py, train.py, active.py, ledger.py
      daemon/     app.py, helper_bus.py, scheduler.py, supervisor.py, routes_*.py
    tests/        fixtures/make_fake_mail.py, make_fake_chatdb.py, golden typedstream blobs
  swift/                         SwiftPM package; one app bundle that grows from helper (M1) to full app (M6)
    Package.swift
    Sources/TARSApp/             main, AppDelegate, DaemonClient (socket + JSON lines), CommandRouter, Supervisor, UI/ (M6)
    Sources/TARSKit/             CalendarService, RemindersService, ContactsService, Notifications, AppleScriptRunner
    Resources/Info.plist         LSUIElement, usage strings for Calendars, Reminders, Contacts, AppleEvents, Notifications
  scripts/                       bundle_app.sh, dev_sign.sh, install_launchagent.sh, download_models.sh, check_no_ai_endpoints.sh
  docs/                          spec PDF, technical-plan.md (snapshot of this doc), PERMISSIONS.md, QUESTIONS.md, adr/
```

Conventions: ruff and mypy strict, explicit return types, early returns over nesting, conventional commits, plain SQL migrations with no ORM. Core dependencies: `fastapi`, `uvicorn`, `httpx`, `pydantic`, `tomlkit`, `sqlcipher3`, `keyring`, `numpy`, `scikit-learn`, `sentence-transformers`, `mlx`, `mlx-lm`, `typedstream`, `typer`, `rich`, `structlog`; `outlines` from M5; `mitmproxy`, `playwright`, `dateparser` from M5 and M7.

### Configuration: tars.toml

One file holds every model choice, threshold and standing permission.

```toml
[profile]
name = "small"                                  # auto-detected from hw.memsize; user can override

[models]
embedding = "BAAI/bge-small-en-v1.5"
tier1     = "heads"                             # heads | jev   (jev = local jeff/von server at jev_url)
tier2     = "mlx:mlx-community/Qwen3-8B-4bit"   # mlx:<hf id> | openai_compat:<url>  (Ollama / mlx_lm.server)
drafts    = "mlx:mlx-community/Qwen3-8B-4bit"
jev_url   = "http://127.0.0.1:8000"

[llm]
idle_unload_s = 600
tier2_daily_budget = 300
fallback_p = 0.8

[cascade]
band = [0.40, 0.60]
vip_always_tier2 = true

[notify]
min_p = 0.75
daily_cap = 12
quiet_hours = ["23:00", "08:00"]

[learning]
reply_fast_minutes = 20
reply_slow_days = 3
maturity_days = 14
example_max_age_days = 180
decay_days = 90

[active_learning]
per_day = 3

[features]                                      # off | shadow | live
drafts = "shadow"
commitments = "off"
booking = "off"
shadow_days = 14
graduate_precision = 0.85

[drafts]
sink = "mail"                                   # mail | inbox

[permissions]                                   # confirm | auto | off; promotions logged and revocable
calendar_create = "auto"

[store]
encryption = "sqlcipher"                        # sqlcipher | none
key_source = "keychain"                         # keychain | file

[egress]
proxy_port = 8081

[paths]
data_dir = "~/Library/Application Support/TARS"
```

## Data model

One SQLite file, `store.db`, in WAL mode, encrypted with SQLCipher by default from M2 onward. The encryption flag ships in M1 and defaults on at M2 because that is the moment six months of personal mail lands in the file. `store/db.py` is the only module that knows: it opens via `sqlcipher3` with `PRAGMA key` set from 32 random bytes kept in the macOS Keychain (`keyring`, service `com.zararutherford.tars`, account `db-key`). `tars db shell` and `tars db sql` open the store with the key, so development never needs the raw `sqlite3` tool. `key_source = "file"` (a 0600 file in the data dir) is the escape hatch if Keychain ACL prompts get in the way.

| Table | Key columns | Notes |
| --- | --- | --- |
| `people`, `identities` | person: `display_name`, `contact_identifier`, `relationship` (professor, friend, family, colleague, vendor, list, unknown), `is_vip`, `is_me`; identity: `kind` (email, phone, imessage), `value`, UNIQUE(kind, value) | Contacts upgrade identities to names; `is_me` is seeded from Sent-mailbox senders. |
| `threads` | `source`, `external_key` (Mail `conversation_id` or chat guid), `subject_norm`, `last_inbound_at`, `last_outbound_at`, `participants`, `calendar_linked` | Follow-up timers compare `last_inbound_at` with `last_outbound_at`. |
| `events` | `source` (mail, imessage, calendar, reminders), `external_id` (Message-ID, message guid, calendarItemIdentifier), `thread_id`, `direction` (in, out, none), `sender_person_id`, `recipients`, `occurred_at`, `subject`, `body` (quotes stripped), `body_raw`, `body_hash`, `meta` json, UNIQUE(source, external\_id) | One row per message even when Mail holds it in several mailboxes; `mail_rowid_map` keeps the ROWIDs. |
| `event_state` | `read_at`, `first_viewed_at`, `deleted_at`, `flagged_at`, `replied_at`, `reply_event_id` | Substrate for implicit signals, filled by the watcher's state pass. |
| `event_embeddings` | `model`, `dim`, `vec` (float16 blob), `content_version` | Source of truth for the in-RAM search matrix. |
| `person_stats` | `n_in`, `n_out`, `reply_rate`, `median_reply_latency_s`, `last_in_at`, `last_out_at` | Tier-1 features. |
| `predictions` | `event_id`, `question`, `tier`, `answer`, `p_raw`, `p_cal`, `model_version`, `mode` (live, shadow), `feature`, `latency_ms` | Every model decision with its inputs hash: the audit record and the raw material for calibration and shadow scoring. |
| `labels` | `event_id`, `question`, `value`, `weight`, `source` (user\_explicit, proposal\_outcome, reply\_latency, false\_negative, draft\_diff, reminder\_outcome, read\_signal, tier2\_weak), `evidence`, `excluded`, UNIQUE(event\_id, question, source) | The training set; `excluded` implements "this was a one-off". |
| `examples` | `event_id`, `question`, `label`, `weight`, `pinned`, `excluded`, `last_used_at` | Few-shot bank for tier 2, rebuilt nightly. |
| `style_fingerprints`, `style_notes` | per person: average words, formality, greeting, sign-off, first-name use, emoji rate, exemplar ids; notes with evidence and weight | From sent mail and draft diffs. |
| `drafts` | `proposal_id`, `person_id`, `thread_id`, `body`, `fingerprint_used`, `mail_rowid`, `state` (created, saved\_to\_mail, sent\_matched, abandoned), `sent_event_id`, `diff` | TARS keeps its own copy so diff harvesting works with every sink. |
| `ledger_rules`, `ledger_tombstones` | rule: `short_id` (`r_0a3f`), `kind` (template name or freeform), `predicate` json, `effect` json, `text_rendered`, `origin` (learned, user, default), `evidence`, `n_support`, `n_contra`, `state` (active, decaying, retired, retired\_by\_user), `last_confirmed_at` | Source of truth for `preferences.md`; tombstones stop the learner from re-deriving a rule the user deleted. |
| `proposals` | `kind` (flag, draft, followup, reminder, calendar, booking, question, graduation, weekly\_note, report), `event_id`, `thread_id`, `feature`, `mode` (live, shadow), `state` (pending, accepted, edited, dismissed, snoozed, expired), `payload`, `rationale`, `one_off`, `shown_at`, `resolved_at`, `resolved_via`, `user_edit`, `shadow_outcome` (tp, fp, fn, tn) | Every state change writes `labels` and `audit_log`. |
| `actions`, `egress_intents`, `permissions` | action: `type`, `payload`, `state` (queued, approved, running, done, failed, cancelled), `approval_token_hash`, `token_expires_at`, `auto_promoted`, `result`; intent: `host`, `methods`, `path_prefix`, `payload_sha256`, `expires_at`, `max_uses`; permission: `mode`, `promoted_at`, `revoked_at` | The single write path. |
| `shadow_runs` | `feature`, `started_at`, `ends_at`, `state`, `threshold`, `n`, `precision`, `recall`, `report` | One row per feature in shadow. |
| `concerns`, `concern_observations` | `title`, `done_definition`, `truth_sources`, `watch_rules`, `cadence`, `status_color`; observations with `kind`, `summary`, `event_id` | Standing concerns. |
| `documents`, `chunks` | file-backed truth sources with chunk embeddings | Used by concerns and chat. |
| `model_versions`, `calibrators` | head and calibrator versions with metrics and an `active` flag; calibrator `method` (platt, isotonic) and `params` | A new version is promoted only if validation does not regress. |
| `watermarks`, `nightly_runs`, `audit_log`, `schema_migrations` | connector cursors; nightly step ledger; audit rows with `actor` (daemon, nightly, helper, user, proxy), `kind`, `ref`, `summary`, `payload`, `prev_hash`, `hash` | `audit_log` is append-only through BEFORE UPDATE and BEFORE DELETE triggers that raise, plus a SHA-256 chain. |

Vector search is numpy, not an extension: embeddings live in `event_embeddings`, and `store/vectors.py` keeps an in-RAM float32 matrix built at daemon start (55k by 384 is about 42 MB; one matmul answers a cosine query in about 10 ms on an M1). This avoids loading a native extension into a SQLCipher connection; `sqlite-vec` is the swap if the corpus outgrows it.

The preference ledger round-trips through `preferences.md`, which is rendered from `ledger_rules` with one line per rule carrying its id and evidence, for example `- [r_0a3f] Never flag mail from list "stanford-digest" — dismissed 14 of 14 (last confirmed 2026-10-12)`. When the file's mtime is newer than the last render (checked on daemon start and nightly): a deleted line retires the rule with a permanent tombstone; an edited template line is re-parsed; anything unparseable becomes `kind = "freeform"`, is fed to tier 2 as an instruction, and renders with the suffix "(applied by reasoning, not as a hard rule)"; a new line without an id becomes a user-origin rule.

## Decision layer

One function, `decide(state, questions)`, answers typed questions with calibrated probabilities, and every backend implements it. The interface matches the Jev wire format exactly, so a local jeff or von server drops in with one config line, and `tars-llm`'s `/v1/slots` endpoint speaks the same shape.

```python
class QuestionKind(StrEnum):
    NOUL = "noul"; CHOICE = "choice"; SCORE = "score"

@dataclass(frozen=True)
class Question:
    key: str
    kind: QuestionKind
    instructions: str
    options: tuple[str, ...] = ()        # choice / score; score options ordered low to high

class Answer(TypedDict):
    answer: bool | str
    p: float                             # calibrated confidence in `answer`
    probabilities: dict[str, float]      # per option; {"yes": p} for noul
    tier: Literal[0, 1, 2]
    p_raw: float
    model_version: str | None

@dataclass
class State:                             # everything a backend may look at
    event: EventView
    thread: ThreadView
    sender: PersonView | None
    features: dict[str, float]           # tier-1 hand features, also rendered as text for tier 2
    examples: list[ExampleView]          # nearest labeled examples, filled lazily for tier 2
    rules_context: list[str]             # freeform ledger lines matching this sender or thread

class DecisionBackend(Protocol):
    name: str
    def decide(self, state: State, questions: Sequence[Question]) -> dict[str, Answer]: ...
    def decide_batch(self, states: Sequence[State], questions: Sequence[Question]) -> list[dict[str, Answer]]: ...
```

`Cascade.decide()` is the only public entry point; `tars decide --paste` calls it. Serialization on the wire is `{"noul": p}`, `{"choice", "probabilities", "confidence"}` and `{"score", "probabilities", "confidence"}`.

### The five questions

| Key | Kind | Instructions | Used for |
| --- | --- | --- | --- |
| `needs_reply` | noul | Does this need a reply from me? | notify, draft |
| `urgency` | score: none, today, this\_week | How soon does it need attention? | notify timing |
| `has_commitment` | noul | Does this contain a commitment or plan? | reminders (M5) |
| `sender_kind` | choice: vip, known, cold, automated | Who is this really from? | weighting, escalation |
| `awaited_reply` | noul | Is this a reply I was waiting for? | closes follow-up timers |

### The cascade

Each tier answers only what the previous tier left unanswered, and every answer is written to `predictions`.

1. Tier 0, rules. A closed predicate DSL stored as JSON: conjunctions over `sender.address`, `sender.domain`, `sender.person_id`, `sender.relationship`, `sender.is_vip`, `event.source`, `event.list_id`, `event.automated`, `event.subject`, `event.hour`, `event.weekday`, `thread.calendar_linked`, `thread.user_participated`, `thread.n_messages`, with operators `eq`, `in`, `regex`, `gte`, `lte`, `present`. An effect fixes one answer with a `p`. The learner writes rules only by filling templates (`mute_sender`, `mute_list`, `vip_sender`, `never_reply_domain`, `calendar_thread_urgent`), which is also how they render to English. Freeform user rules are never evaluated as tier 0.
2. Tier 1, embedding plus heads. `BAAI/bge-small-en-v1.5` (384 dimensions) over `subject + body[:1500]`, concatenated with about 30 standardized hand features: sender stats, thread state, time of day and weekday, content cues (a question mark, a date or time pattern, length bucket, To versus Cc, recipient count), Mail's `automated_conversation` and `list_id_hash` flags, and a source one-hot. One `LogisticRegression(class_weight="balanced")` per question (multinomial for choice and score), persisted with joblib and registered in `model_versions`. About 1 ms per event after embedding.
3. Escalation. Tier 2 runs when any tier-1 `p_cal` falls inside `cascade.band`, or when `sender_kind` is vip, subject to `llm.tier2_daily_budget`. Overflow is queued for the nightly run on AC power, with the tier-1 answer standing meanwhile.
4. Tier 2, Qwen via `mlx_lm` in-process with slot scoring. The prompt holds the thread, a sender summary, the three nearest labeled examples and any matching freeform rules, within about 1,000 tokens, with the static preamble prompt-cached. It ends with a JSON skeleton. TARS emits the fixed text itself and, at each value slot, runs one forward step and reads the logits restricted to the first token of each allowed option: the answer is the argmax and `p` is the softmax over the allowed options. The output is constrained by construction and the probability is real. Thinking mode is off. Realistic latency on this Mac is 3 to 6 s per call. For backends without logits (`openai_compat`, meaning Ollama or `mlx_lm.server`) the fallback is enum-constrained JSON with Pydantic validation and one retry, with `p` fixed at `llm.fallback_p`. Tier-2 answers are written as `labels` with source `tier2_weak` and weight 0.3, overridden by any later real signal.
5. Calibration. Per question and tier: Platt scaling below 500 resolved pairs in the trailing 30 days, isotonic regression above; ECE and Brier are logged to `model_versions.metrics`. The escalation band applies to `p_cal`.

## Senses

Connectors are read-only watchers that open each source's own database and never write back. Each implements `poll(cursor) -> (items, cursor)` plus `state_pass(since)` for mutable fields; `normalize.py` resolves people (exact identity match, else a new person), builds threads, computes `body_hash` and queues embedding. The watcher loop runs every 60 s.

| Connector | Strategy |
| --- | --- |
| Mail | Detect the highest `~/Library/Mail/V*/MailData/Envelope Index` (V10 here; `[mail] root` overrides). Open with `mode=ro` and `uri=True`, never `immutable=1`, because new mail sits in the `-wal` file until checkpoint. Poll `messages WHERE ROWID > :wm AND deleted = 0 ORDER BY ROWID LIMIT 500`, joining `addresses`, `subjects`, `mailboxes.url`, `recipients` (To and Cc) and `message_global_data.message_id_header`. Dedupe on Message-ID across mailboxes. Direction is `out` when the sender is an `is_me` identity or the mailbox leaf is Sent. Body: locate `<ROWID>.emlx` or `.partial.emlx` by the path rule with an index cache and a scoped walk on miss; the first line is a byte count, then RFC822 parsed with `email.parser.BytesParser` and the default policy, then a trailing plist to ignore. Prefer `text/plain`, else HTML to text; strip quoted blocks and "On ... wrote:" into `body`, keeping `body_raw`. A second pass each cycle over the last 7 days diffs `read`, `date_last_viewed`, `deleted` and `flagged` into `event_state`. Thread is `conversation_id`, with `message_references` as the fallback. |
| Messages | `chat.db` read-only the same way. Poll `message.ROWID > :wm` joined to `chat_message_join`, `chat` and `handle`. Skip tapbacks (`associated_message_type != 0`) and group events (`item_type != 0`). `occurred_at = date / 1e9 + 978307200`. Body is `text` when present, else `attributedBody` decoded with the `typedstream` library and a short heuristic fallback; decode failures are counted (target under 0.5 %). Direction is `is_from_me`; for group messages from the user, use `other_handle` or the chat participants. Thread is `chat.guid`. `is_read` and `date_read` feed `event_state`. M8 reuses this connector with a self-chat filter. |
| Calendar, Reminders, Contacts | Through `TARS.app`: EventKit (`EKEventStore`) for calendar and reminders, and the Contacts framework (`CNContactStore`, not EventKit) for contacts. macOS has no change tokens, so the app observes `.EKEventStoreChanged` and `.CNContactStoreDidChange` and posts `eventstore.changed`; the daemon then issues `calendar.query` (minus 30 to plus 90 days), `reminders.query` and `contacts.dump` and diffs by identifier and `lastModifiedDate`. A 10-minute poll covers missed notifications. Calendar items become events with `occurred_at = start` and direction `none`; reminders become events with `meta.completed_at`; contacts populate `people` and `identities`, not events. `threads.calendar_linked` is set when a mail thread's subject matches a calendar title or its attendees overlap the thread's participants. In M1, before the socket bus exists, \`TARS.app --dump calendar |
| Documents (M5.5) | Files the user hands TARS, such as a program sheet or a lease: PDF and markdown text extraction, chunk and embed, re-index when the mtime changes. |

## Learning loop

Everything the user already does is a label, and the nightly job turns those labels into a better tier 1 without the user teaching TARS explicitly. `tars-nightly` runs an ordered list of idempotent steps recorded in `nightly_runs.steps`; a crash resumes at the failed step, and every harvest insert uses `INSERT ... ON CONFLICT(event_id, question, source) DO UPDATE`.

1. harvest\_reply\_latency. For inbound events past `maturity_days` or already replied, find the first outbound event in the same thread after `occurred_at` (mail also matches `In-Reply-To` and `References`). Within 20 min: `needs_reply = yes` weight 1.0 and `urgency = today` weight 1.0. Within 24 h: yes 0.9, today 0.5. One to three days: yes 0.8, this\_week 0.7. Later: yes 0.7, none 0.6. No reply after 14 days from a human sender with no outbound in the thread: `needs_reply = no` weight 0.4, weak on purpose. Writes `event_state.replied_at`.
2. harvest\_false\_negatives. Replied inbound events with no live flag or draft proposal and `p_cal(needs_reply)` under 0.5 become `needs_reply = yes` weight 2.0 and are counted in the morning report.
3. harvest\_proposal\_outcomes. Accepted or edited: positive 1.0. Dismissed: negative 0.8, or 1.0 if dismissed within 5 s. Expired unseen after 48 h: negative 0.3. `one_off` sets `labels.excluded = 1`.
4. harvest\_read\_signals. Deleted unread within 60 s: `needs_reply = no` 0.5. Flagged by the user in Mail: yes 0.9. First viewed within 5 min of arrival: weak urgency 0.3.
5. harvest\_draft\_diffs (M4). Drafts in state `saved_to_mail` are matched to the outbound event in the same thread within 7 days; `difflib` ratio, paragraph deletions and greeting or sign-off changes become `style_notes` for that person, and the draft moves to `sent_matched`.
6. harvest\_reminder\_outcomes (M5). Completed or deleted within 5 s of firing: `has_commitment = no` 0.8. Snoozed twice or more then completed: yes 1.0 plus a timing note.
7. refresh\_person\_stats, refresh\_threads, refresh\_fingerprints. Fingerprints come from outbound events grouped by recipient; a new contact gets the nearest fingerprint by relationship type.
8. rebuild\_examples. Drop examples older than `example_max_age_days` unless pinned, drop excluded ones, dedupe near-duplicates (cosine over 0.95), cap per class.
9. train\_heads. Per question, one label per event resolved by priority user\_explicit, false\_negative, proposal\_outcome, reply\_latency, read\_signal, tier2\_weak; labels older than 365 days at half weight; a time-based split with the last 14 days as validation; metrics against the baseline "flag everything from humans"; the new version is promoted only if validation PR-AUC is at least the active version's minus 0.01.
10. recalibrate, as described in the decision layer.
11. score\_shadow\_runs, described below.
12. update\_ledger. Reconcile `preferences.md` edits first; mine template rules (at least 8 outcomes from a sender or list with at least 90 % agreement); confirm rules with fresh supporting evidence; decay rules with no support for `decay_days` to `decaying` (effect weight 0.5, rendered "(fading)"), and after 180 days to `retired` with a 30-day tombstone; then rewrite `preferences.md`.
13. tier2\_batch\_backlog. Run the day's over-budget escalations on AC power.
14. pick\_active\_learning. Up to `per_day` events with `p_cal` nearest 0.5, one per sender, become `question` proposals shown between 09:00 and 21:00; answers are `user_explicit` labels with weight 3.0.
15. write\_report. One audit line and, if anything changed, a `report` proposal.

Shadow mode is a registry, not a flag. `proposals/shadow.py` holds one `Feature` per behavior (`drafts`, `followups`, `commitments`, `booking`) with its mode from `[features]`, `shadow_days`, `graduate_precision`, and a `truth(proposal)` function over the harvest tables that returns tp, fp, fn, tn or none (for drafts: did the user reply to that thread within 3 days?). Shadow proposals are created with `mode = shadow` and are never notified or executed. When the window ends and precision clears the threshold, a `graduation` proposal appears: "Follow-up drafts would have been right 87 % of the time (41 of 47). Turn on?" Accepting edits `tars.toml` through `tomlkit`, preserving comments, and is audited; revocation takes the same path.

Cold start (M2): `tars backfill --months 6` runs the Mail and Messages connectors from cursor 0 within the window, embeds (bge-small on MPS at roughly 500 documents per second), runs steps 1, 7, 8, 9 and 10 over the window, and prints metrics against the baseline. Twelve months is a config change.

## Actions and the confirm gate

Every write to the outside world passes through one path: a proposal the user accepts, a permission check, a one-time token bound to the exact payload, an executor, and an audit row. For `mail_send` and `booking` the proposal payload is the final preview, so acceptance is the explicit confirm.

[diagram in the living doc: confirm gate · proposal to executor, two decisions]

A dismissed proposal only yields a label; an accepted one becomes an action that runs only with a token minted after the permission check or the user's confirm.

The token is 32 random bytes, stored as a SHA-256 hash with a 10-minute TTL and bound to `payload_sha256`; every executor refuses to run without a live token. Promotions to auto-run are themselves proposals ("Always add calendar events?"), are audited, and are revocable in the ledger view.

| Action | Executor |
| --- | --- |
| `mail_draft` | `AppleScriptRunner` in TARS.app. For replies, Mail's `reply` on the original message keeps `In-Reply-To` and `References`; the original is located via `meta.mailbox_url` and the Message-ID. Otherwise `make new outgoing message` with `visible:false`, add the recipient and sender, then `save`. TARS then reads the Envelope Index for the new Drafts row (subject match within 10 s) into `drafts.mail_rowid`, which later reveals when it was sent. Fallbacks in order: a `visible:true` compose window, a `mailto:` URL, "Copy draft". With `drafts.sink = "inbox"` the draft stays in TARS until accepted. |
| `mail_send` | `send` on the saved draft. Off by default and never auto. |
| `reminder_create`, `calendar_create` | EventKit writes through TARS.app. `calendar_create` is the obvious first promotion to auto. |
| `messages_send` (M8) | AppleScript `send ... to participant`, only to the self-chat or dedicated handle. |
| `booking` (M7) | Playwright Chromium launched with the proxy set to `127.0.0.1:<egress.proxy_port>` and loopback bypass disabled. Per-site recipes (`recipes/opentable.py`, `recipes/dmv.py`) declare the allowed write endpoints. |

### Egress gate

`egress/mitm_addon.py` runs inside `mitmdump`. GET, HEAD and OPTIONS pass after the leak filter. POST, PUT, PATCH, DELETE and WebSocket upgrades require a matching egress intent that the daemon registers when an action is approved (`host`, `methods`, `path_prefix`, `payload_sha256`, `expires_at`, `max_uses`). Intents rather than a header, because a browser form submit cannot carry a custom header. The leak filter is a Bloom filter of 6-word shingles from the last 30 days of event bodies plus all contact names, emails and phone numbers, rebuilt hourly; the URL and decoded body are normalized and checked, and a hit blocks unless the request matches an approved intent (a booking legitimately contains the user's own name and phone). Every block is written to `audit_log` with actor `proxy`. All TARS processes also get `HTTP_PROXY` and `HTTPS_PROXY` pointed at the proxy. Enforcement outside the app: a Little Snitch or LuLu rule set (deny all egress for `TARS.app`, `tars-daemon`, `tars-llm` and Chromium; allow `mitmdump` only) from M7, and a Network Extension content filter at M9 once a Developer ID exists.

### No-AI-endpoint check

`scripts/check_no_ai_endpoints.sh` runs in pre-commit and CI. It fails on hostnames (`api.openai.com`, `api.anthropic.com`, `api.typesafe.ai`, `generativelanguage.googleapis.com`, `openrouter.ai`, `api.mistral.ai`, `api.cohere.ai`, `api.groq.com`, `api.together.xyz`) anywhere in `engine/`, `swift/` and `scripts/`, and on package names in `uv.lock` (`openai`, `anthropic`, `google-generativeai`, `cohere`, `mistralai`, `litellm`, `langchain*`), because hostnames live inside SDKs. Model weights are fetched only by `scripts/download_models.sh`, a user-initiated read.

## Standing concerns

A concern is a durable goal TARS takes custody of so the user can stop carrying it, and the design goal is fewer interruptions: one trusted "you're fine" a week beats fifty reminders.

- A concern is added in chat. Tier 2 runs a short intake to fill the four parts (what done looks like, where the truth lives, what to watch for, how often to report) and writes a `concerns` row.
- Watch rules are typed predicates evaluated nightly and on matching events: `deadline_without_receipt(days=3)`, `amount_changed`, `thread_quiet(days)`, `new_evidence(similarity at least 0.6)`, `date_within(days=30)`. Hits become green or amber `concern_observations`.
- On Sunday at 18:00 one `weekly_note` proposal is rendered by tier 2 from the week's observations, one line per concern. All green collapses to three words. Onboarding states once that silence between notes means nothing is wrong.
- Truth sources the user hands over (a program sheet, a lease, a decision file) are ingested through `senses/documents.py` and cited by id.
- TARS never pays anything, never contacts anyone without an approved draft, and never marks a requirement satisfied without a `documents` citation. Ambiguity renders as "I'm not sure this counts; check with your advisor."

## Compute profiles

The profile is auto-detected from `hw.memsize` on first run and only sets model names, the escalation band, the draft context size and the nightly scope; everything else is the same code.

| Profile | Memory | Tier 1 | Tier 2 | Band | Nightly |
| --- | --- | --- | --- | --- | --- |
| small (this Mac) | 16 GB | bge-small + logistic heads | Qwen3-8B 4-bit (about 5 GB) or Qwen3.5-4B 8-bit | 0.40 to 0.60 | retrain heads |
| medium | 32 to 64 GB | jeff / GLiFormer 400M (`tier1 = "jev"`) | Qwen3 30B-A3B or 32B 4-bit | 0.35 to 0.65 | heads + embedding fine-tune |
| large | 96 to 192 GB | fine-tuned 1 to 2B decision model | Qwen3 70B+ 8-bit | 0.25 to 0.75 | LoRA on tier 2 (MLX native) |

MLX in-process is the default runtime. `openai_compat` is the fallback behind the same interface; Ollama's llama.cpp backend honors JSON-schema `format`, which the slot-scoring fallback relies on.

Memory budget on 16 GB: Qwen about 5 GB, the torch embedder about 1 GB, Chromium about 1 GB, next to Mail and Xcode. The LLM unloads when idle, the nightly job runs as a separate process, and the small profile never runs tier 2 and Playwright at the same time. The embedder can be swapped to `mlx-embeddings` to drop torch entirely.

## Milestones

Each milestone is a straight-line dependency on the one before and ends with the spec's demo; the first one that counts is M3, when TARS notices an important email, pings the user, and has a draft waiting by M4. Shadow mode gates M4, M5 and M7: each runs silently against real traffic for two weeks before it may act. Detail is deepest for M-1 through M3, which are built first.

[diagram in the living doc: roadmap · M-1 to M9 with three shadow-mode gates]

The three behaviors that act on the user's behalf each run silently for two weeks before they are allowed to act.

| Milestone | Work items | Done when | Main risk |
| --- | --- | --- | --- |
| M-1 Repo bootstrap (half a day) | `git init`; `engine/pyproject.toml`, `.python-version` 3.12, `uv sync`; ruff, mypy, pytest; `swift/Package.swift` with `TARSKit` and `TARSApp`, `Resources/Info.plist`, `scripts/bundle_app.sh`, `scripts/dev_sign.sh`; `tars.toml.example` and `config.py` with profile auto-detect; `scripts/check_no_ai_endpoints.sh`, pre-commit, CI; `docs/technical-plan.md` snapshot, ADRs for IPC and encryption | `make check` passes on an empty engine and a signed empty `TARS.app` launches | None; keep it to half a day |
| M0 Engine runs | `llm/server.py` (`tars-llm` on `run/llm.sock`): `mlx_lm.load` of Qwen3-8B-4bit, `/health`, `/v1/chat/completions` streaming, `/v1/slots`, `/v1/unload`, idle unload; `llm/backends/{mlx_inproc,openai_compat}.py`; `scripts/download_models.sh`; `brain/types.py`, `questions.py`, `tier2/{prompt,slots,client}.py`, `cascade.py` with tier 2 as the only backend; `tars decide --paste`; `tests/test_slots.py` | A pasted email returns typed JSON for all five questions | Slot decoding against `mlx_lm`'s KV cache (trim and reuse between slots); fallback is one constrained generation of the whole object with per-slot probabilities read from the sampled-token logits |
| M1 Senses | `store/db.py`, `migrations/0001_init.sql`, `store/keychain.py`, repos; `senses/{base,watcher,normalize}.py`, `mail/{envelope,emlx,quotes,html}.py`, `messages/{chatdb,typedstream_decode}.py`, `eventkit/`; `people/resolve.py`; `daemon/{app,helper_bus,scheduler,supervisor}.py`, `routes_events.py`; `TARSApp/{main,DaemonClient,CommandRouter}.swift`, `TARSKit/{CalendarService,RemindersService,ContactsService,AppleScriptRunner}.swift`, `--dump` mode; synthetic DB fixtures and golden typedstream tests; `docs/PERMISSIONS.md`; `tars doctor` | `tars events --since 1h` prints the last hour across all sources | TCC attribution: prove early that `tars-daemon` spawned from `TARS.app` reads the Envelope Index once FDA is granted to the app; typedstream coverage |
| M2 Cold start + tier 1 | `embed/sentence_transformers_backend.py`, `store/vectors.py`, `people/stats.py`, `brain/tier1/{features,heads,train,calibrate}.py`, `brain/examples.py`, `brain/rules/{dsl,engine,render}.py` with default rules, the full cascade; `learning/{nightly,harvest_reply_latency,harvest_read_signals,train}.py`; `tars backfill`, `tars train`, `tars eval`; encryption defaults on; `docs/QUESTIONS.md` | Tier 1 beats "flag everything from humans" on held-out history; `tars eval` prints PR-AUC and precision and recall at the operating point on a time split | Reply-latency label noise; mitigated by weights, false-negative labels and the eval harness |
| M3 Notify | `proposals/{engine,states,notify}.py`, `routes_proposals.py`; `TARSKit/Notifications.swift` with Accept, Dismiss and One-off actions; `TARSApp/Supervisor.swift`; `scripts/install_launchagent.sh`; `learning/{harvest_proposal_outcomes,active}.py`; `audit.py`; `tars today`, `tars proposals` | TARS pings about a real important email before the user sees it | Notification fatigue in week one; ship with `notify.min_p = 0.75`, a daily cap and quiet hours |
| M4 Drafts (shadow first) | `drafts/{engine,diff,followups}.py`, `people/fingerprints.py`, `actions/{runner,tokens,permissions}.py`, `executors/mail_draft.py`, `learning/harvest_draft_diffs.py`, `proposals/shadow.py`. First task: spike `reply` plus `save` on macOS 26 | A TARS draft to a professor goes out with fewer than three edits | AppleScript `save` behavior on macOS 26 |
| M5 Commitments (shadow first) | `brain/tier2/extract.py` (Outlines with `mlx_lm`, schema `Commitment{what, when, who, kind}`), `commitments/{extract,schedule}.py` with `dateparser` anchored on the event timestamp, executors `reminder.py` and `calendar.py`, `learning/harvest_reminder_outcomes.py` | TARS catches a plan the user had forgotten | Date resolution ("Thursday", "tonight"); the resolved date is shown in the proposal |
| M5.5 Standing concerns | `concerns/{model,watchers,weekly_note}.py`, `senses/documents.py`, chat intake in the CLI | One Sunday note reports the seeded concerns correctly, green or amber | File-based truth sources need a parser per file type; start with PDF and markdown only |
| M6 Desktop app | `TARSApp/UI/{MenuBar,ProposalInbox,Chat,Ledger,Today}.swift` over the socket API with streaming chat; permission walkthrough; `tars db encrypt` for stores created before M2 | The terminal is no longer needed | Scope: the inbox and the ledger view are the product, chat is secondary |
| M7 Actions (shadow first) | `egress/{mitm_addon,leakset}.py`, `executors/browser.py`, `recipes/{opentable,dmv}.py`, Little Snitch or LuLu rule set | TARS books a dinner after the user replies "yes" | Site changes; recipes are expected to rot |
| M8 Phone | `phone/bridge.py` over the Messages connector plus `messages_send` | "What's on tomorrow" texted from the car gets an answer | The dedicated Apple ID conflicts with M1's mirroring; see Risks |
| M9 Productize | Installer (`TARS.app` bundle containing the daemon venv), permission walkthrough UI, profile auto-detect UI, Developer ID signing and notarization, signed updates with a local public key, Network Extension, `VACUUM INTO` encrypted backups, export and import of ledger, heads and examples, CI gate finalized | One other person runs it | Needs an Apple Developer account for signing and the Network Extension |

## Top risks and spikes

The two risks that can stall the first milestones are constrained decoding on MLX and macOS permission attribution; both get a day-one spike.

1. Constrained JSON on MLX. The stock server ignores schemas (verified). Mitigation: in-process slot decoding, spiked on day one of M0; Outlines only for M5 extraction.
2. TCC attribution and signing churn. Ad-hoc signatures reset grants on every build, and a launchd-owned daemon would need its own Full Disk Access. Mitigation: a self-signed stable identity, `TARS.app` as the daemon's parent, and an M1 spike proving inheritance.
3. Tier-2 latency. Expect 3 to 6 s per call on an M1 Pro, not the spec's 2 s. Mitigation: tight contexts, a cached preamble, a daily budget, and the nightly backlog.
4. Mail and Messages schema drift and WAL visibility. V10 today; columns can change with macOS. Mitigation: `mode=ro`, never `immutable`; a startup schema probe that marks optional columns; synthetic fixtures so tests never touch real data.
5. typedstream coverage. Edited messages, mentions and rich links may decode oddly. Mitigation: the library plus a heuristic fallback and a failure counter in `tars doctor`.
6. Memory on 16 GB. Mitigation: idle unload, nightly as a separate process, never tier 2 and Playwright together; the embedder can move to `mlx-embeddings` to drop torch.
7. M8's dedicated Apple ID conflicts with M1. Messages.app can sign into one iMessage account; if that is the dedicated ID, `chat.db` stops mirroring the user's own texts. Recommendation: use the user's own account and an iMessage self-chat with a `TARS:` reply prefix; keep the dedicated-ID design for a second Mac.
8. Draft privacy. Mail syncs Drafts to the provider. Accepted per the user's decision; `drafts.sink = "inbox"` exists for the alternative.

## Verification

Every milestone is verified by the spec's own demo plus automated tests that never touch real data.

- Unit and integration: `uv run pytest` in `engine/` with synthetic Envelope Index and `.emlx` trees and a synthetic `chat.db`; golden tests for Jev-shaped serialization; cascade tests with fake backends; a `needs_models` marker for tests that load Qwen.
- Per milestone: M0 `tars decide --paste` returns typed JSON; M1 `tars events --since 1h`; M2 `tars eval` beats the baseline; M3 a real notification whose Accept and Dismiss round-trip into `labels`; M4 a sent draft with fewer than three edits; M5 a caught plan; M5.5 a correct Sunday note; M6 a day without the terminal; M7 a booking after "yes"; M8 a text answered from the car.
- Security: the endpoint check in pre-commit and CI; egress tests asserting that a POST without an intent is blocked and logged and that a GET containing a recent subject line is blocked; `tars doctor` prints permission and encryption state; an `audit_log` chain verification command.
- Learning loop: `tars nightly --now --dry-run` prints each step's counts; `tars shadow status` shows precision per feature; `tars eval` runs nightly and reports against the human-sender baseline.
