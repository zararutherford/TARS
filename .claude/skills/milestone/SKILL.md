---
name: milestone
description: Run one TARS milestone (M-1, M0, M1 ... M9) from the technical plan. Use only when the user names a milestone id.
argument-hint: [milestone-id]
disable-model-invocation: true
---
Work on milestone $ARGUMENTS of TARS.

1. Read the milestone's row (work items, "Done when", main risk) from `docs/technical-plan.md` if it exists, otherwise from the Claude Doc linked in CLAUDE.md using the Docs tools. Also read the sections it depends on (Architecture, Data model, Decision layer, Verification).
2. Restate the "Done when" criterion in one sentence and list the files you expect to create or touch. Flag any plan detail that is ambiguous or that the current machine contradicts. Wait for approval before writing code.
3. Implement in small steps. After each step run the relevant check (`uv run pytest` in `engine/`, `swift build` in `swift/`, or `make check`). Use fixtures, never real Mail or Messages data.
4. Stop when the "Done when" command passes. Report what passed, what was skipped, and any deviation from the plan.
5. Do not commit. Suggest a conventional-commit message and the plan-doc updates the milestone implies.
