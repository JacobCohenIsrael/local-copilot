# Next image-preparation operation

17 October 2026. Preparation only; no image layer was downloaded, expanded,
imported or executed. Compilation and model loading remain disabled.

Execution update: the owner approved the exact operation below, which ran once
and stopped with an authentication HTTP_FRAMING_INVALID fault before accepting
payload bytes. The attempt is consumed; worker/reader exit is confirmed. See
[IMAGE_STAGE_RESULT.md](IMAGE_STAGE_RESULT.md). This review is preserved as the
approved operation record and does not authorize a retry.

Later update: the corrected authentication transport and separate unused successor
are reviewed in [IMAGE_AUTH_RECOVERY_REVIEW.md](IMAGE_AUTH_RECOVERY_REVIEW.md).
The original failed attempt and its approved code remain preserved. That new
review requires a new attempt approval; none has been recorded.

## Completed prerequisite: temporary WSL2 policy

The owner approved and we applied `wsl-build-limits.proposed` to
`C:\Users\yaki_\.wslconfig`. The destination previously did not exist; an
exclusive create prevented overwriting a newly appearing file. Its SHA256 is
`acb3b77283695020316e28498f0ba08440de05b3907c945f7006c756ed1314de`.
Docker had no running containers and only docker-desktop was running in WSL.
Docker Desktop stopped, WSL shut down, and Docker Desktop restarted successfully.

Verified after restart:

| Setting | Effective observation |
| --- | --- |
| Logical CPUs | 1 |
| VM memory cap | 6 GiB configured |
| Docker usable memory | 6,215,266,304 bytes, about 5.79 GiB |
| Guest swap | 0 bytes |
| Probe exit/removal | Exit 0, removal confirmed |

Less usable memory than the configured cap reflects VM/kernel overhead; the
separate compiler limit stays 4 GiB. The saved receipt is an observation, not
future authority: recheck the actual VM before each live operation.

Approval: `wsl-policy-approval.json`. Application and verified-restart evidence:
`.runtime/wsl-policy/8c26adaaf9a447df9af27319745e14d4/`.
The read-only cached-image swap/storage proof is
`.runtime/image-storage/348333bf6a0947dcad05b7725dfbfae1/result.json`.
Its probe used 0.5 CPU, 64 MiB, no GPU/network and was removed.

Rollback restores prior absence after stopping Docker/WSL: remove only this exact
file if its hash still matches, then restart and verify. Preserve any owner
edits; a changed hash means stop and review rather than delete. The limits remain
active until restoration is requested or agreed as part of the workload cleanup.

## Exact operation ready for approval

The acquisition, expansion, source admission and process guard are now connected
and tested. The old 8187e5fd preparation snapshot is preserved as history.
The executable review remains disabled, SHA256:
`861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323`.
Its machine-readable path is
`.runtime/guarded-image-review/861efd0ff5481c569c1cd13a29bb38ec13878696174448cb443e0ceff1960323/review.json`.
It binds the exact image descriptors, current helper hashes, interpreter path/
executable hash/version, CPU evidence and proposed image-scope controls. Changing
those inputs invalidates approval. Windows/Python remain trusted host runtimes.

The operation is **one attempt to download the pinned image blobs and verify
compressed hashes plus expanded stream hashes, without import or execution**.
No real layer has been downloaded or expanded. `image-stage-approval.json` is
now present following the owner's explicit decision; the one attempt has been
consumed. `image-stage-approval.template.json` remains deliberately disabled and
is not authority. Preserve the fault and claim; no automatic retry or reset.

| Proposed control | Exact operation |
| --- | --- |
| Image | Linux amd64, `nvidia/cuda@sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c` |
| Pinned bytes | Eleven compressed layers plus configuration, 3,951,095,908 bytes (~3.95 GB) |
| Accepted HTTP bodies | At most 5 GiB including bounded authentication bodies; not a wire/TLS/header cap |
| Staging namespace | 7,918,969,032 bytes including partials/receipts; 4 MiB reserved for supervisor records |
| Free disk reserve | 20 GiB, checked before admission and within bounded copying; not a physical reservation |
| Stream expansion | At most 16 GiB total and per layer, <=64 KiB output chunks, no tar extraction/output |
| Windows staging job | One logical processor by job affinity, 128 MiB committed memory, one process |
| CPU start | <=92 C continuously for ten seconds, at most 90 seconds waiting; no worker/network before eligibility |
| CPU stop | >=97 C, any known throttling, invalid/stale/missing source or lost monitor/controller |
| Unknown hardware throttle | Remains null; proposed acceptance only for this image operation |
| Reader | Hash-pinned existing ASUS reader, 1,920 samples; remaining lifetime checked before starting work |
| Work deadline | 1,800 seconds shared by download and verification; <=600 seconds per blob |
| Independent progress | Worker lease 7.5 seconds; monitor/controller liveness 2.5 seconds |
| Stopping | Cooperative cancellation then owned-job termination, one five-second worker exit-confirmation budget |
| Attempts | One fixed durable claim, including failed baseline/setup/unfinished/successful attempts; no reset or automatic retry |

Affinity is set and queried before any child instruction executes, using
[Windows job limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information).
The child also reports its one-bit effective affinity in native fixtures.
Multiple processor groups are rejected. This limits this worker's scheduling;
it does not limit unrelated Windows apps or guarantee physical power/temperature.
The passive reader has its existing separate 256-MiB/four-process job; the
supervisor/reader overhead is outside the staging job. Windows paging is unchanged.

## Connected execution and fail-closed behavior

The real command rejects missing approval before any reader, process, blob socket
or live claim is created. After approval it checks current WSL configuration and
Docker limits, obtains a fresh cached-image read-only swap/storage proof, checks
Windows disk headroom and claims `.runtime/guarded-image-stage/` exactly once.
The reader establishes fresh source/sequence/query/age/coverage and the baseline.

The parent rechecks exact approval/helpers immediately before launch. An immutable
start record binds the child to the claim; mutable Windows state files are not
used for this handoff. The child rechecks approval before constructing the fixed
anonymous `nvidia/cuda` registry source. Only pinned descriptors and reviewed
service/CDN origins are accepted; no Docker/credential files or bearer tokens are
logged. Accepted bytes are size/hash checked before cache promotion.

A separate liveness thread can terminate an already-owned job when the monitor
loop stalls, including while child I/O is blocked. Kill-on-close covers abrupt
owner death. A child also checks its parent's changing pulse during cooperative
work. Continuous CPU monitoring remains active through stream verification and
result checks. No monitor-loss path falls back to unsupervised work.

Exit 0 is insufficient: the parent checks complete compressed/expanded receipts,
review hash, scope, ordered identities and total bytes, and confirms worker exit
and reader stop before returning COMPLETE. Faults return a nonzero CLI exit.
Metrics and structured state/results are retained; corrupt or partial results
cannot enable import. Stopping uses owned handles and frozen limits, never a
fresh approval-file read. It precedes fault-journal I/O so a full disk cannot
delay that path. If persistence/exit fails, the durable unfinished claim still
denies restarting; it is never converted to success or silently cleared.

## Source acceptance for this scope

The same passive evidence and independent endpoint/decoding corroboration are
bound by source-evidence SHA256
`56a94d0f4f1dd13062078a2d7326bd4fd7e64749ab0268de6790c80fc8d0749f`.
No additional manual comparison is requested. Raw reader frames stay
validatedCpuSensor=false and hardware throttle stays null. Only an image-scoped
permit can qualify a copy; synthetic or foreign frames are rejected.

The limitation requiring acceptance for this operation is:

> Firmware refresh latency and calibration are not independently guaranteed;
> acceptance is for one monitored image download/stream-verification attempt,
> never import, compilation or model runtime.

The proposed image-only thermal/unknown-throttle policy SHA256 is
`91a3b97106d67b81466606b46a27742c2df6849ffe39f7d5d54d133ffb732483`.
The numeric start/stop values match the earlier build decision. That build-only
acceptance does not automatically extend to this image workload; the new approval
must explicitly cover this scope and its missing throttle channel. This review
does not activate it. Software/OS/driver/storage failure can defeat intervention;
no physical thermal cutoff or hardware calibration guarantee is claimed.

## Validation and entry points

**198 proposal tests pass**, including exact approval/scope/helper changes,
real-format ten-second baseline/97-C faults, missing/unknown/known channels,
reader coverage, receipt substitution, journal/stop failures and job-limit refusal.
**Fourteen native connected cases pass**: success, hot/stale/lost feed, cancellation,
blocked read/expansion, monitor stall, partial/bad-hash results, reader-stop failure,
controller lease loss, no cool baseline and abrupt owner death. Every started
worker exited; all retries were rejected. The deliberately failed reader-stop
fixture stays FAULT. No actual sensor, network, image or GPU was used in these cases.
Native baseline/deadline timings are shortened fixture controls; unit checks use
the full proposed baseline and real-format frames. These tests are not proof of
hardware calibration, download compatibility/performance or a safe physical cutoff.

Final native evidence:
`.runtime/guarded-image-rehearsals/394e5fe82a094d7f8f66d2067f032f1d/result.json`.
Longest recorded detection-to-exit confirmation was about 0.522 s; abrupt owner
death about 0.006 s. These are fixture observations, not future worst-case bounds.
The full supervisor rehearsal passed image staging, dummy build/export and
OpenCode with scripted API replies in about 74 s; originals stayed unchanged and
all workers stopped. Evidence:
`.runtime/local-worker/daa4aa0769b84700be2e9bd45c2a1ec5/result.json`.
One earlier run preserved a dummy-suite receipt publication fault after its
workers were removed; immutable per-case receipts fixed that Windows failure.

Commands from the project root:

```powershell
python -B local_worker.py review-image
python -B local_worker.py rehearse-image
```

`prepare-image` regenerates the disabled packet. Once explicitly approved,
`run-image` is the one-attempt entry point from an administrator shell required
by the ASUS reader; it does not self-elevate. `cancel-image` signals only the
owned active stage. The actual no-approval command was checked: exit 3,
IMAGE_STAGING_NOT_APPROVED, no live claim/process/socket created.

Docker import remains separate: it needs active backing-volume confirmation,
fresh headroom, concrete daemon disk/stop controls and its own approval. Stream
size is not a Docker import disk quota. No import, build, engine, model, firmware,
power/fan setting or existing D:\AI configuration change belongs to this operation.
