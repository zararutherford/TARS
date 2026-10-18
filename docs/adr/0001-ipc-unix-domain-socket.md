# ADR 0001: IPC over one Unix domain socket, no listening port

Date: 2026-10-17. Status: accepted (M-1).

## Context

TARS has three processes that must talk: `TARS.app` (Swift, the single TCC principal and the
daemon's parent), `tars-daemon` (Python, everything that thinks), and `tars-llm` (Python,
in-process `mlx_lm`). The `tars` CLI also needs the daemon. A hostile web page in the user's
browser must not be able to reach any of them, and the auth story must stay trivial for a
single-user machine.

## Decision

- The daemon hosts one Unix domain socket at
  `~/Library/Application Support/TARS/run/daemon.sock`, mode 0600. Filesystem permissions are
  the authentication. No TCP port is ever opened.
- CLI to daemon: HTTP/1.1 and JSON over the socket (`httpx.HTTPTransport(uds=...)`, uvicorn
  `--uds`).
- `TARS.app` to daemon: newline-delimited JSON over the same socket via `Network.framework`
  (`NWConnection` with `NWEndpoint.unix`), so the Swift side needs no HTTP library.
  Daemon-to-app commands are `{id, kind, args}`; app-to-daemon events are
  `notification.action`, `eventstore.changed`, `contacts.changed`, `chat.message`, plus
  command results.
- Daemon to `tars-llm`: a second socket `run/llm.sock` exposing `/health`,
  `/v1/chat/completions`, `/v1/slots`, `/v1/extract`, `/v1/unload`.
- `TARS.app` spawns `tars-daemon` as a child, so TCC attributes the daemon's reads to the app
  and one Full Disk Access grant covers both. The daemon never runs as its own LaunchAgent.

## Consequences

- A Little Snitch or LuLu rule can deny the daemon all network access outright without
  breaking anything.
- Swift holds no business logic; it renders, routes commands, and supervises.
- `uv sync` replacing the Python binary does not invalidate any TCC grant, because the grant is
  on the app bundle, keyed on the stable bundle id `com.zararutherford.tars`.
- Streaming to the app is line-delimited, not SSE; the CLI gets SSE-style streaming through
  HTTP.
