# Useful coding task 2: reject negative read limits

19 October 2026. **Prepared offline; fresh owner approval required. No live run.**

## Concrete task and expected patch

The pilot's 113-byte patch correctly changed VALUE to 2. Its adapter hardcoded
the selected filename, synthetic original and complete replacement. The successor
keeps that host-brokered OpenCode edit path, adding one fixed insertion task.

`containers/worker/task_bundle.py:bounded_read` currently calls
`stream.read(maximum + 1)` without first rejecting a negative maximum. With -2,
this becomes `read(-1)`, reading the whole file before the subsequent size check
rejects it. This defeats the read-time bound. Offline fake-stream checks reproduce
the defect without reading a large real file.

Select only that existing repository file (9,293 bytes), SHA256
`33594c6162ce6e0916071a97e390d4d042c5b25ce1512a26f39df3b2c9e7279d`.
Stage it as `task_bundle.py` in a fresh bundle and worker input directory. The
repository original and an unselected sentinel remain outside the containers.
This is the expected change, **an example only, not a returned model patch**:

```diff
 def bounded_read(path, maximum=MAX_FILE_BYTES):
+    if maximum < 0: raise ValueError
     plain(path)
```

Codex/OpenCode task, exactly:

```
Only edit task_bundle.py: insert a guard at the start of bounded_read to raise ValueError when maximum < 0, before file access. Preserve all other bytes. Do not run commands or access other files.
```

Compact Strata prompt, exactly (52 UTF-8 bytes):

```
Return only Python: if maximum < 0 raise ValueError.
```

The model supplies the guard; the adapter accepts only one `if maximum < 0`
containing one `raise ValueError` or `raise ValueError()`. It removes an optional
Python fence, indents the generated text and inserts it at the pinned function
header, using the original newline convention. It cannot manufacture a missing
guard, change the comparison, add behavior or replace other source bytes.
OpenCode applies the resulting replacement to its disposable selected file.
This fixed task proves no general coding quality or native model tool calling.

## Exact proposed limits

- One new model attempt, one Strata request, at most two OpenCode provider calls.
  No retry, restart or fault reset. Earlier ten model attempts stay consumed.
- Same pinned model, engine, dependencies and Docker images as the pilot.
  WSL one CPU / 6 GiB / no swap; model one CPU / 4 GiB / no extra swap.
  Context 512; output allowance 32 tokens; temperature 0; thinking disabled.
- The pinned upstream server reserves **eight additional context tokens** and
  refuses overflows without truncation (`fit_max_tokens` is disabled). Actual
  rendered/tokenized prompt must therefore be at most **472 tokens**. The
  inspected no-tools, thinking-disabled template produces 121 ASCII bytes for
  this prompt: a conservative byte-level tokenizer upper bound of 121 input
  tokens, or 161 including output reserve and runtime margin. This is a bound,
  not a measured token count. Retain actual usage from the one live response.
- Request deadline 90 s; engine silence limit 75 s; model/container lifetime
  300 s; existing outer/model-controller and worker deadlines 410 s; worker
  subprocess completion 400 s. Startup retains its existing 180 s ceiling,
  subject to the shorter overall lifetime. Nothing extends these limits.
- Worker 0.5 CPU / 512 MiB / no extra swap; 64-MiB tmpfs; no network/GPU;
  read-only root/input/bridge; UID 65532; 64 processes; dropped capabilities;
  no privilege escalation, sockets, ports, credentials, shell or other-file access.
- Generated guard at most 128 bytes. Selected/output file at most 65,536 bytes;
  total selected/output bytes at most 131,072; returned patch at most 65,536.
  Provider requests at most 65,536 bytes; model response at most 16,384;
  worker result at most 32,768. Worker stdout/stderr tightened to 8,192/4,096
  bytes so the larger real-file result has room. Exceeding a bound faults.
- Valid startup telemetry for ten seconds; existing warning targets unchanged.
  CPU emergency stop **97 C**, GPU **75 C**, GPU power **100 W**, VRAM
  **14,336 MiB**, host RAM used **28,672 MiB**; existing AC/throttle, clock,
  source and freshness checks remain enforced. Host/guest leases and freshness
  stay 2.5 s. Preserve source calibration/refresh/throttle limitations.
- No downloads, installs, builds, configuration/resource/power/firmware changes,
  private-engine/disk operations or global Docker/WSL stopping.

The pilot needed 59.6897 s prompt processing and 22.7602 s generation. This
different request can still time out or produce an inadmissible guard. That
consumes the attempt; it does not authorize a larger deadline or another call.

## Acceptance and evidence

Require all of the following before reporting a successful live milestone:

1. One real Strata answer; preserve raw response, actual prompt/completion usage,
   native timing/logs and source/configuration identities. Prompt plus 32-token
   reserve plus eight-token runtime margin fits the effective 512-token window.
2. Exact response hash reaches the worker. Its edited file equals the adapter's
   mechanically inserted model guard; every pre-existing source byte is intact.
   Missing, malformed, excessive or extra code fails closed.
3. Deterministic function checks reject -1/-2/-65,536 **before** any fake path,
   validation, open or read access; ordinary reads at 3/4/default remain correct;
   0/1/2 still reject a three-byte file. These are acceptance checks, not model
   execution or a fresh thermal observation.
4. Collect only `task_bundle.py`; review the returned patch and run
   `git apply --check` against the untouched selected snapshot. No automatic
   repository application. Verify repository original, disposable original and
   unselected sentinel unchanged. The host withholds a patch if the repository
   original changes, output lineage fails or worker stop is unconfirmed.
5. Model stops after generation, before edit delivery. Independently inspect
   the two owned container IDs: stopped, PID 0, exit/OOM status retained. Inspect
   the saved parent, watchdog, reader and administrator-wrapper PIDs after exit.
   Save raw evidence even on failure. A normal host result alone is insufficient
   to claim that independent shutdown inspection has happened.
6. Preserve result/returned patch, exact inputs/helpers, readings, faults,
   inspection receipts and a SHA256 inventory in this new review directory.
   Verify all preceding model/build evidence unchanged. Retain containers;
   stop only this operation's owned components. Do not reset any fault.

Offline checks cover response rejection, insertion/byte preservation, patch
applicability, selected-file import, wrong-response lineage, changed repository
original, owned stopping with a fake Docker client, and approval refusal before
any Docker access. **513 offline checks passed**: 366 proposal/supervisor,
88 runtime/integration (including seven new useful-task tests), 59 worker.
No simulator rerun or live inference is claimed for this preparation.

## Review and approval boundary

Safe main-CLI commands:

```
python -B local_worker.py review-useful-coding-task
python -B local_worker.py review-coding-task
```

`prepare-useful-coding-task` creates a new offline snapshot; do not reprepare
the chosen packet after approval. `run-useful-coding-task` requires a matching
fresh `coding-task-2-approval.json` and Windows administrator access for the
existing CPU source. That file is intentionally absent. `cancel-useful-coding-task`
uses the same owned model cancellation path; the worker retains its own lease.

Final review SHA256:
`549cb02957572957e23f1cc8346803ee3bbb3bef1c924bdf6ff2e64ef4d161e8`.
Packet: `.runtime/strata-coding-2-review/549cb02957572957e23f1cc8346803ee3bbb3bef1c924bdf6ff2e64ef4d161e8/review.json`.
Its helper snapshot includes the adapter, task specification, common supervisor and CLI.
New namespaces are `.runtime/strata-coding-2-model`, `strata-coding-2-worker` and
`strata-coding-2-preparation`; they cannot reuse the pilot's spent namespaces.
Earlier offline preparation packets are preserved and confer no approval.

Fresh approval would authorize **only this one useful coding operation and its
existing monitoring, owned stopping and independent evidence collection**.
It would not authorize patch application, a retry, context expansion or Hermes.

## Checkout byte restoration

Offline checks exposed CRLF checkout conversion of two hash-pinned readers and
four historical approval files. Their LF bytes were restored to the exact
existing reviewed hashes/unchanged archived originals; no script logic, decision,
scope, consumed state or safety policy changed. `.gitattributes` now preserves
those six files' LF bytes. Converted approval copies are retained under
`.runtime/checkout-byte-restoration-2026-10-19/`. Historical `.runtime` evidence
was not rewritten, and neither reader was executed.
