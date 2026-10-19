# Bounded coding-task intake — offline only

The [request-gate milestone](REQUEST_GATE.md) adds offline call/token/time
admission logic with 15 new tests. It has no model connection or HTTP listener;
the container proposal below remains disabled.
The [HTTP rehearsal](HTTP_REHEARSAL.md) now tests that core over actual loopback
connections to an owned fake backend; 16 integration tests and two CLI checks
passed. It cannot connect to Strata or run OpenCode.
The [Linux OpenCode compatibility check](OPENCODE_COMPATIBILITY.md) now runs the
verified CLI in a capped, network-disabled container against fake loopback
servers. It passed; no model was loaded or file edited. The live worker recipe
remains disabled. The worker regression suite now has 48 passing tests.
The [file action checks](OPENCODE_ACTIONS.md) add a real CLI edit of a synthetic
file and blocked shell/external/unlisted-file requests. Title generation is
disabled in the proposal; file permission resources use verified relative
paths. All 51 worker tests pass. Strata remains off.
The [complete bundle rehearsal](BUNDLE_REHEARSAL.md) now connects task selection,
the fake-only Docker worker and host-side patch collection in one command.
The original files stayed unchanged; all 59 worker tests pass.

`task_bundle.py` prepares a disposable copy of explicitly named UTF-8 files and
collects a bounded patch for cloud review. It has no process launcher, Docker
client, HTTP client, GPU access, Strata startup, or OpenCode invocation. No
original file is changed and patches are never automatically applied.

The fixed **offline test envelope** is eight existing files, 64 KiB per file,
128 KiB total input/output, a 4,000-character task, and a 64 KiB patch. These
limits are independent of token counts; they do not establish that an engine
context will fit. This is not a new approved live safety policy.

An orchestrator supplies a JSON request with exactly these fields:

```json
{
  "sourceRoot": "C:\\absolute\\path\\to\\disposable-project",
  "files": ["src/example.py"],
  "task": "Fix the specified small issue; change only the supplied file."
}
```

From the Local Copilot project:

```powershell
python -B containers/worker/task_bundle.py prepare --request <request.json>
python -B containers/worker/task_bundle.py collect --run-id <returnedRunId>
```

Both commands return JSON; rejection exits with code 2. Prepare returns the
isolated workspace location under `.runtime/worker-bundles/<runId>/workspace`.
Collect returns the patch, changed file names and byte counts, with execution
and model flags false. No worker currently edits that workspace; tests edit
only disposable fixtures. `codingPerformed: false` means no AI coding ran.

Only named existing files are copied. Changes and deletions are supported;
new paths are rejected. Collection rejects unexpected entries, binary/control
content, growth past the caps, links/junctions, multiple hard links, changed
baseline hashes, and invalid run IDs. Traversal, Windows device/stream names,
case aliases and `.git`, `.agents`, `.codex` paths are rejected before staging.
Original paths and unselected project files are not copied into the bundle.
Incomplete sessions and collected bundles stay on disk for inspection; there
is no automatic cleanup or continuation.

The host orchestrator and staging directory are trusted. Baseline and manifest
must stay outside any future worker mount. These file checks are not an OS
sandbox against a malicious concurrent host process; pathname check/open races
are not eliminated. Do not run an untrusted executable directly on the host.
The future container must mount only `workspace`, never the original project,
baseline, host credentials, or Docker socket. Input selection and explicit
review are still responsible for excluding secrets.

Eight offline tests passed, including real Windows hard-link rejection and
Git patch checks for Unicode/space paths, missing final newline, CRLF, and
empty-file deletion. The sandbox denies creating hard links, so that test run
used approved host execution against workspace-local temporary fixtures.

Remaining before an actual local coding task: the approved engine build and
runtime; a pinned OpenCode container; model-specific token admission;
deadline, tool/call/output budgets and cancellation; telemetry/watchdog
integration; persisted global FAULT handling; and post-exit collection through
this boundary. No actual OpenCode CLI syntax or isolation is verified by this
offline milestone. MCP remains optional.

## Disabled OpenCode container proposal

`opencode_plan.py --run-id <runId>` validates a pristine task bundle and emits
an execution-disabled configuration/container proposal as JSON. It writes
nothing, starts nothing, and cannot approve a policy. Three additional tests
pass (11 total): scoped permissions, control/credential-file rejection, and
changed-workspace rejection. `.opencode`, `.claude`, `AGENTS.md`, `CLAUDE.md`,
OpenCode project configs and `.env` files cannot be supplied to this adapter.

The installed Windows package metadata identifies `@opencode/cli` version
2.0.26 from `anomalyco/opencode`; this is a Linux version candidate, not a
verified Linux artifact at the proposal stage. A matching musl binary and two
runtime libraries have since been staged and tested by the compatibility check
above. `Dockerfile.proposed` still needs an assembled context including those
libraries before any approved build; no image was built or pulled.
The default image entrypoint refuses execution. A Docker entrypoint is not an
authorization boundary; the eventual host supervisor must enforce admission.

The proposed worker has a read-only root, non-root user, capped CPU/RAM/tmpfs,
no GPU/ports/restart, and only workspace/config mounts. Its provider points to
`request-gate`, not directly to Strata. That proxy and its isolated network do
not exist yet; no deployable launch command is generated. The served model ID
is an explicit unresolved placeholder. Config context/output values are
proposals and are not enforced token accounting.

The draft uses OpenCode's documented [JSON run output and download-disable
switches](https://opencode.ai/docs/cli/), [provider allowlist and config
options](https://opencode.ai/docs/config/), and [OpenAI-compatible
provider](https://opencode.ai/docs/providers/). Its [permissions](https://opencode.ai/docs/permissions/)
deny every tool by default, allowing reads/edits only of named workspace paths.
Shell, delegation, network tools and interactive questions stay denied.
The [two-step agent setting](https://opencode.ai/docs/agents/#max-steps) is a
convenience limit: a final text response can still follow. The future proxy
must independently enforce exact token admission, call count, response size
and deadlines. Effective settings and denial behavior still require testing
inside the pinned container. Configuration files merge; a custom file alone
does not guarantee isolation from other configuration sources.
