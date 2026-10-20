# Useful coding task 2: failed before container creation

19 October 2026. **One approved attempt consumed; no retry. No patch produced.**

The owner approved the exact
[task review](CODING_TASK_2_REVIEW.md), review SHA256
`549cb02957572957e23f1cc8346803ee3bbb3bef1c924bdf6ff2e64ef4d161e8`.
Approval was bound to that existing packet; it was not regenerated.

The administrator wrapper launched once. The first operation, creating the
isolated OpenCode worker, failed because Docker's Linux engine named pipe
`dockerDesktopLinuxEngine` did not exist. The API call never reached a daemon.
The fault was latched in `.runtime/strata-coding-2-worker/attempt.json` and
`integration-result.json`. No container ID or creation receipt was returned.

No worker or model container was started, no model/API request was made, no
CPU reader/watchdog/capacity probe was launched, and no edit was performed.
There is no returned patch to preserve or apply. Repository target, selected
snapshot, unselected sentinel and staged task bundle remain unchanged.
Docker was not started or restarted. No workload or policy limit was changed.

## Independent exit checks

Independent Windows inspection confirmed that parent PID **42380** and
administrator wrapper PID **42660** had both exited. The Docker Linux named
pipe was absent and no Docker Desktop/backend process was observed.

A separate read-only `docker inspect` of the exact intended worker name also
failed to connect to that missing endpoint. Fresh container inspection is
therefore **unavailable**; this is not a claim of a successful running-container
shutdown inspection. The recorded create failure establishes that this call
created/started no container, and the independent checks establish host exit.

The wrapper's exit record contains `null`, not a numerical exit code. Preserve
that limitation: do not infer exit 0 or 3 from it. The terminal CLI fault,
matching integration receipt and independent process checks are retained.

## Evidence

Directory:
`.runtime/strata-coding-2-review/549cb02957572957e23f1cc8346803ee3bbb3bef1c924bdf6ff2e64ef4d161e8/`.

- Original review and frozen helpers, owner approval copy and binding.
- One launch-dispatch record, exact wrapper and administrator PID receipt.
- Independent host and Docker postchecks.
- Launch stdout/stderr/process/exit records and the consumed worker fault.
- Original model API package inputs and inventories of prepared worker inputs,
  original/sentinel and task bundle; no returned patch file is fabricated.
- Structured `execution-result.json` and SHA256 `execution-preservation.json`.

Preservation SHA256:
`7a8838a0f40b4af513b2dfb03a4e6caee03797ccdf2978dfbe221eb5a8f35354`.
Execution-result SHA256:
`cdc11ab666b2f3e9da6aacb47c89528dcb398868056e171fcd437ff17156b178`.

All ten preceding model attempts, build evidence, model/configuration identities
and existing settings were checked unchanged using the recorded guards. The
model-attempt count remains **ten**, since this failure never reached a model
attempt. The separate useful-task-2 operation approval and worker attempt are
**spent**. Do not delete/reset the fault or reuse this approval.

The 513 pre-execution offline checks remain separate from this real failed
dispatch. No new real inference, thermal result, coding success or context
capacity was established. Any successor needs a new review and fresh explicit
approval; the owner's instruction forbids a retry of this operation.

After preservation, a read-only status correction makes
`python -B local_worker.py review-useful-coding-task` report `ATTEMPT_CONSUMED`
when the worker namespace exists, even if no model namespace was created.
It does not authorize a launch or reset anything. Frozen helpers retain the
exact sources used for the failed execution; this later correction is offline.
All nine useful-task offline checks passed afterward, including two new status
checks. The preserved failure inventory was verified again without rewriting it.
