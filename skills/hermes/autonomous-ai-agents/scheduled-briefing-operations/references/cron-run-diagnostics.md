# Cron Run Diagnostics

Use this after a manual trigger, a missed delivery, or a suspicious job status. The purpose is to identify which of four layers failed: trigger, execution, artifact, or delivery.

## Evidence Checklist

Record these separately:

| Layer | Evidence | Healthy signal |
|---|---|---|
| Trigger | Job list and scheduler/gateway status | Enabled, scheduled, gateway running, expected next run |
| Execution | Durable execution attempts | At least one relevant attempt is `completed` |
| Artifact | Persisted output file or stored final response | Non-empty report with expected sections/data |
| Delivery | Delivery log and configured destination | Explicit success to a resolvable target |

A single green field does not prove the other layers.

## Compact Command Sequence

Use the current official CLI syntax if it has changed.

```bash
hermes cron list
hermes cron status
hermes cron runs <job_id> --limit 10
```

Then inspect the task-correlated gateway/agent log entries and the job's output directory:

```text
$HERMES_HOME/cron/output/<job_id>/
```

Resolve `$HERMES_HOME` from the active profile; do not hardcode the default profile path.

## Decision Tree

### A. No run attempt exists

1. Confirm the gateway/scheduler is running.
2. Confirm the job is enabled and `state=scheduled`.
3. Confirm `next_run_at` and timezone.
4. Confirm a manual run was queued for the next scheduler tick rather than assumed synchronous.

### B. Latest attempt says `Fire claim was not acquired`

1. Compare timestamps with earlier attempts.
2. If an earlier attempt overlaps and later completes, classify this as duplicate-trigger suppression, not job failure.
3. Avoid another manual trigger until the active run finishes.
4. Investigate stale claims only when no overlapping successful/active attempt exists.

### C. Execution completed but no message appeared

1. Find the persisted report first; verify generation succeeded.
2. Inspect the delivery log for `skipping delivery`, missing origin/home channel, or target-specific errors.
3. Read the stored job delivery target.
4. If `origin` is unresolved on Desktop/CLI/TUI, choose a target that exists:
   - `bot-chat` for the profile's canonical Bot Chat;
   - explicit `platform:<chat_id>:<thread_id>` when delivery belongs on a gateway platform;
   - `local` when file-only output is intended.
5. Update and read the job back.

### D. Execution failed before a report exists

1. Identify the task-critical failure rather than listing every warning.
2. Check provider/MCP authentication for the actual source.
3. Check whether the prompt requested interactive-only or approval-requiring behavior.
4. Prefer direct read-only provider tools for unattended data collection.
5. Re-run once after correction and verify a real artifact.

## Log Interpretation Notes

- `Job ... completed successfully` proves agent execution, not delivery.
- `deliver=origin but no origin or home channels` means the artifact is valid but the route is not.
- Unrelated MCP initialization warnings are not the root cause when the task-critical MCP calls and final response succeeded.
- A blocked nonessential tool is not fatal if an allowed path completed the source query and the report exists.
- Durable run history is the authority for distinguishing separate attempts; timestamps in the job summary alone can conflate them.

## Completion Report Template

```markdown
- Trigger: healthy / unhealthy — evidence
- Execution: completed / failed — run ID and timestamp
- Artifact: present / missing — path or handle
- Delivery: delivered / skipped / failed — destination and reason
- Next run: timestamp and timezone
- Configuration changes: exact fields changed and read-back result
```
