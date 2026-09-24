# T96 Player History and Head-to-Head Field Audit

## Goal

Close the field-audit gap left by T95: trace canonical `HeadToHead` and the service results (`HeadToHeadResult`, `PlayerResults`) through API-Tennis mapping, bounds/availability, REST and chat consumers. Fix only defects proved by a focused regression; document unknown provider semantics rather than guessing.

## Evidence and scope

- Official [API-Tennis REST documentation](https://api-tennis.com/documentation) describes `get_H2H` as returning `H2H`, `firstPlayerResults`, and `secondPlayerResults`; it documents no result-count limit. The project applies its own ten-row fetch bound.
- Inspect the provider DTO/mapper, service/cache, REST schema/route, chat tool output, and player-results UI. Record each public/canonical field, ordering/identity, empty meaning, freshness, truncation, and downstream use in the T95 matrix.
- Suspected defect to prove: `get_head_to_head` marks data `partial` only when `meetings` reaches the ten-row fetch bound, even if either per-player recent-results list reaches that bound.

## Steps

1. Add a service regression with fewer than ten meetings and ten first-player recent matches; run it and confirm it fails because availability is `available` rather than `partial`.
2. If confirmed, make the smallest change so any internally capped list reaching the bound makes the aggregate availability `partial`; retain existing orientation, caller `limit`, cache, and response shape.
3. Add/adjust boundary coverage for each list and for uncapped responses; inspect that invalid/unmapped provider rows and empty arrays do not fabricate matches or fields.
4. Extend the field matrix for `HeadToHead`, `HeadToHeadResult`, and `PlayerResults`, including exact REST/chat/UI behavior and any semantics not documented by the provider.
5. Run focused service/provider/API/chat/player-results tests, the deterministic backend suite where possible, Ruff on changed Python files, and `git diff --check`.

## Constraints and completion

- Do not run `init`, start services, call the live API, read or change `.env`, or touch `.next`; the user chose to stop unrelated Colima containers and the application stack remains off.
- Do not widen product behavior, increase provider calls/limits, persist history, or introduce new UI. Preserve all existing/untracked user changes.
- Close only with the exact regression and verification evidence recorded in `CURRENT.md` and `ROADMAP.md`; push the task commit to `origin/main` per repository workflow.
