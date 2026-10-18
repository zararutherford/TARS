---
paths:
  - "swift/**"
---
# Swift rules
- `TARSApp` is a thin client over one Unix domain socket (JSON lines). It renders, routes commands, and supervises the daemon. No decisions, scoring, or scheduling here.
- `TARSKit` wraps Apple frameworks only: EventKit, Contacts, UserNotifications, AppleScript. Each service is a small protocol with a testable fake.
- `Resources/Info.plist` carries `LSUIElement` and the usage strings for Calendars, Reminders, Contacts, AppleEvents, Notifications. Add a usage string before touching a new framework.
- The app spawns `tars-daemon` as a child so TCC grants are inherited. Never spawn it from launchd or a shell directly in production paths.
- Sign with the self-signed stable identity via `scripts/dev_sign.sh`, never ad-hoc `codesign -s -` (TCC grants would not persist).
- Swift 6 language mode, strict concurrency. Explicit types on public API.
