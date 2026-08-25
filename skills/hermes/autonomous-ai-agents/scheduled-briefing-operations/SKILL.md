---
name: scheduled-briefing-operations
description: "Use when creating or diagnosing recurring agent briefings."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [cron, scheduled-jobs, briefings, delivery, diagnostics, mcp]
---

# Scheduled Briefing Operations

Use this skill for recurring agent-produced briefings: Jira work queues, inbox digests, project status reports, monitoring summaries, and similar scheduled reports that must gather live data, reason over it, preserve continuity, and reliably reach the user.

This skill complements the protected `hermes-agent` skill. Load `hermes-agent` and its current cron/background-system reference first; official Hermes docs remain authoritative for commands and fields.

## Goals

A finished scheduled briefing has four independently verified properties:

1. **Trigger:** the scheduler and gateway will fire the job at the intended time and timezone.
2. **Execution:** the agent can authenticate, query the source, paginate completely, and finish unattended.
3. **Artifact:** a real report was generated and persisted.
4. **Delivery:** the artifact reached a destination that exists for the surface where the job was created.

Never collapse these into one status. A scheduler may report `ok` while a duplicate execution attempt failed, or execution may complete while delivery is skipped.

## Creation Workflow

### 1. Make the prompt self-contained

Cron sessions are fresh and cannot ask the user questions. Include:

- exact source/site or tenant identifier;
- verified user/account/project identifiers where available;
- read-only versus write permissions;
- complete query scope and pagination requirement;
- fields to extract and dependency/link traversal rules;
- explicit uncertainty language (`需確認`, `unknown`, etc.);
- output sections and sort order;
- timezone;
- behavior for authentication failure or empty results;
- instruction not to fabricate missing data.

For recurring briefs that compare with the previous run, enable continuity and tell the prompt exactly which changes to surface.

### 2. Validate the live source before scheduling

Use a read-only call to prove:

- the integration is authorized;
- the target tenant/site is accessible;
- human-readable names resolve to exact provider IDs;
- at least one representative query works.

Persist exact IDs in the job prompt when stable, while retaining a safe lookup fallback. Do not guess or normalize identifiers.

### 3. Create the job with explicit operational fields

Set at least:

- name;
- schedule;
- self-contained prompt;
- repeat behavior;
- continuity when needed;
- delivery destination;
- session attachment only when the chosen destination supports it.

After creation, read the job back and verify `enabled`, `state`, `schedule`, `next_run_at`, `deliver`, and `continuity`.

### 4. Verify scheduler prerequisites

Check gateway/scheduler status after creation. If the gateway is not running, the job is durable but inactive. On macOS, an installed launchd gateway is appropriate for recurring local jobs; verify the supervised PID/status after installation or start.

Do not declare the automation active merely because the job record exists.

### 5. Test once and inspect all four layers

A useful smoke test checks:

- durable run attempts, not only the job's `last_status`;
- task-critical tool calls and source pagination;
- final persisted report;
- delivery result or explicit skip reason.

For unattended jobs, prefer direct provider/MCP tools over workflows that depend on interactive approvals. If a blocked tool is nonessential and an allowed direct tool can complete the work, continue with the allowed path and verify the final artifact.

## Delivery Rules

- `origin` works only when the job record contains a resolvable origin/home channel. Desktop, CLI, or TUI creation can leave `origin` unset even though the job was created from a conversation.
- For the current profile's canonical Bot Chat, use `bot-chat` when that is the intended destination.
- For reliable external delivery, use an explicit platform target, including chat/thread identifiers when applicable.
- `local` intentionally saves without sending.
- After changing delivery, read the job back. The write response alone is not sufficient verification.

Treat these as separate outcomes:

- **execution failed** — no valid report;
- **execution completed, delivery skipped/failed** — valid saved report, transport problem;
- **delivery succeeded** — report reached the destination.

## Run-Diagnosis Workflow

1. Read the job list for high-level state and gateway status.
2. Inspect durable run attempts (`hermes cron runs <job_id>` or the current documented equivalent).
3. Correlate attempts by run ID and timestamp.
4. If one attempt says `Fire claim was not acquired`, look for an earlier overlapping attempt before diagnosing the job as broken. This normally means the at-most-once claim prevented duplicate execution.
5. Inspect logs only after durable attempts establish which run matters.
6. Confirm the final response was written under the cron output store or other configured artifact destination.
7. Check delivery logs separately; a successful agent turn can still say delivery was skipped because no origin/home channel resolved.
8. Fix the transport or job configuration, read it back, and only then report the final state.

See [references/cron-run-diagnostics.md](references/cron-run-diagnostics.md) for the compact decision tree, evidence checklist, and command sequence.

## Briefing Quality Checklist

- [ ] Complete pagination is asserted from provider response metadata, not inferred from a convenient count.
- [ ] Every factual item carries a source key/link when available.
- [ ] Actionable work excludes completed items and explicit blockers.
- [ ] Missing dependency metadata is labeled for confirmation rather than treated as ready.
- [ ] Related roles and tasks are followed through provider-native links.
- [ ] First run is declared a baseline; later runs compare against continuity context.
- [ ] Old backlog without current scheduling evidence is not automatically promoted as today's work.
- [ ] The final summary distinguishes report generation from report delivery.

## Pitfalls

- **Trusting only `last_status`:** it summarizes the job lifecycle and can hide a failed duplicate attempt or a skipped delivery.
- **Assuming “created from this chat” means `origin` is resolvable:** verify the stored origin/delivery route.
- **Triggering repeatedly while the first run is active:** the duplicate may fail to acquire the fire claim even though the original completes normally.
- **Reporting transient warnings as the root cause:** correlate warnings with the task-critical run and final artifact first.
- **Calling the job active before checking the gateway:** persistence and execution readiness are different states.
- **Using names where provider IDs are required:** resolve once with a live lookup, preserve exactly, and retain a lookup fallback.
