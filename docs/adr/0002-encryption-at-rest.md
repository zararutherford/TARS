# ADR 0002: Encryption at rest with SQLCipher, key in the Keychain

Date: 2026-10-17. Status: accepted (M-1); default flips on at M2.

## Context

`store.db` will hold six months of the user's mail and messages, model decisions, and the
learned ledger. The machine is single-user with FileVault, but the file is still readable by
any process running as the user, lands in backups, and may be copied for debugging. The spec's
non-negotiable is that nothing leaves the machine; at rest the file should be useless without
the user's keychain.

## Decision

- One SQLite file in WAL mode, encrypted with SQLCipher through `sqlcipher3`, which ships
  cp312 macOS arm64 wheels.
- `store/db.py` is the only module that opens the database and the only one that knows the
  key. Nothing else calls `sqlite3.connect`.
- The key is 32 random bytes kept in the macOS Keychain via `keyring`, service
  `com.zararutherford.tars`, account `db-key`, set with `PRAGMA key` on every connection.
- `[store] key_source = "file"` (a 0600 file in the data dir) is the escape hatch if Keychain
  ACL prompts get in the way; `[store] encryption = "none"` exists for fixtures and tests.
- The `[store] encryption` flag ships in M-1 with default `none` and flips to `sqlcipher` at
  M2, the milestone where real history first lands in the file. `tars db encrypt` (M6)
  migrates stores created before then.
- `tars db shell` and `tars db sql` open the store with the key so development never needs the
  raw `sqlite3` tool against an encrypted file.

## Consequences

- Backups (`VACUUM INTO`, M9) are encrypted by construction.
- The `audit_log` chain and triggers live inside the encrypted file; tampering requires the
  key.
- `sqlcipher3` is a dependency from M1, not M-1; M-1 only reserves the config keys.
- Losing the Keychain item loses the store; the nightly job will warn when the item is
  missing, and `tars doctor` prints the encryption state.
