# Complete task-bundle rehearsal

**A single command now selects a synthetic file, runs the real OpenCode CLI
against the fake model, and collects a host-validated patch.** Strata stays off.
The original selected file and an unselected fixture file remain unchanged.

```text
Synthetic original -> task_bundle copy -> read-only container input
                                             |
                                OpenCode edits scratch copy
                                             |
                              bounded exported file contents
                                             |
                          confirmed container exit and removal
                                             |
                            host validates/imports bundle copy
                                             |
                              task_bundle.collect -> review patch
```

The container never mounts the original, baseline or host bundle directory.
Only the selected synthetic `example.py` and bounded task text accompany the
existing pinned binary/libraries/helpers. Results return as encoded bytes.
Host import accepts only that named UTF-8 file, under its byte limit, after
confirmed cleanup and a successful fake-only worker result. A fresh collection
check rejects baseline or workspace changes before import. Originals are
fingerprinted again before the result is returned. Patches are not applied.

`bundle_rehearsal.py` accepts only the staged artifact and an explicit
`--execute-fake-only` flag. It creates its own fixed fixtures; it accepts no
real project, arbitrary task, model, command or upstream endpoint.
The extended verifier accepts a prepared synthetic bundle only for its fixed
fake-edit path. No writable host workspace mount or policy change was added.

## Verified result

- Native run: `PATCH_FOR_REVIEW`, original unchanged, cleanup confirmed.
- Only change: `VALUE = 1` to `VALUE = 2` in the disposable `example.py`.
- Collected Git patch: 113 bytes; two fake requests; no model, OOM or handler errors.
- All 59 worker tests passed. Eight new tests cover real bundle/patch collection
  with a stubbed worker, Git patch validity, invalid exports, byte/text limits,
  baseline/workspace tampering, missing cleanup/bundle proof and interruption.
- One full native Docker rehearsal verifies the unstubbed path described above.

Native evidence:
`.runtime/bundle-rehearsals/00b01b6a858d448686e1f5cc7049645c/result.json`.
Its bundle is `.runtime/worker-bundles/07ae26041bcc4739be73cd8a77aa12ef`.
The source, baseline, disposable output and receipts remain available for review.

```powershell
python -B containers/worker/bundle_rehearsal.py --artifact <staged-musl-artifact> --execute-fake-only
```

Exit 0 means a review patch was returned. Exit 3 means FAULT and no accepted
patch. Results record phases, worker receipt, original-file checks and patch
metadata. Failed runs are not reused or reset by this command.

The existing envelope is unchanged: no network/GPU, 0.5 CPU, 512 MiB RAM/no
extra swap, 64 processes, read-only root/input, 64 MiB scratch, six-second
OpenCode timeout and ten-second inner deadline. No dependencies were downloaded
or installed for this step, and no host project or original configuration ran.

## Remaining live gates

This is a fixed synthetic task with scripted tool requests and token counts.
It does not enable real-model work or arbitrary project tasks. Trusted host
staging is assumed; pathname races against a malicious host are not eliminated.
The result snapshots are evidence, not an atomic production recovery journal.
Host-loss cleanup and a durable global FAULT/watchdog remain unfinished.

The dry-run task path is now connected. Next settle the CPU-only Strata build
admission policy and missing validated hardware channels for owner review.
Compilation/model launch and live policy changes still require explicit approval.
