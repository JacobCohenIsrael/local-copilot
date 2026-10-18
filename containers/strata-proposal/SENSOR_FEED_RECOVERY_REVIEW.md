# Sensor-feed correction and retained-cache verification

17 October 2026. **Approved and consumed.** The worker started, then stopped on
SENSOR_FEED_ERROR: permission denied reading sample 71. Worker/reader shutdown
is confirmed; verification did not complete. See
[VERIFICATION_RESULT.md](VERIFICATION_RESULT.md). Downloads, import, compilation
and model execution remain disabled. Both prior attempts remain unchanged in
latched FAULT. The review below is the preserved pre-execution operation record
and does not authorize another attempt.

## Diagnosis: established limits and corrected defects

All **262 saved frames pass offline replay** through the old feed/gate with a
mock live reader. The final raw reading was 95 C, with no frame error and about
1,658 seconds of declared coverage. The bounded historical Application-event
window contained no matching event. No new hardware reading was taken.

The original catch block discarded the underlying exception and reader exit
code. The **historical root cause cannot be proved** from that evidence. This
change does not claim that the reader cannot fail again, or establish a physical
sensor defect, overheating, or memory exhaustion.

Two software defects are corrected:

1. A frame's consumed sequence and receipt time previously advanced before
   checking reader liveness and source qualification. A rejected frame could
   therefore appear consumed internally. These values now commit only after
   every check passes; a rejected frame never refreshes liveness.
2. Feed exceptions previously collapsed to SENSOR_FEED_ERROR with no detail.
   The guard now preserves fixed reason, operation/phase, last consumed/pending
   sequence, observed reader exit code and numeric OS/Windows error codes.
   It captures these in memory and journals them **after worker/reader stopping**.
   Arbitrary exception text, file paths and credentials are not included.

Injecting reader exit at frame 262 into the archived old implementation
reproduces its generic fault and internal sequence 262 while only 261 frames
were delivered. The corrected implementation stops with sequence 261 and records
READER_EXITED plus the injected exit code. This is a deterministic reproduction
of a possible failure path, **not proof of the original cause**.

No stale/missing/error reading is ignored or substituted. No automatic retry,
reader restart, extra sensor source, memory-cap increase or policy relaxation
was added. A future feed error still consumes the attempt and stops work.

Offline receipts, under
`.runtime/verification-recovery/7ce23bea0a5848529330874891b08013/`:
`offline-replay.json` and `injected-exit-comparison.json`. Their hashes are bound
in the new executable review. No downloaded blob body was read by preparation.

## Preserved attempts and input

- Original auth failure: `.runtime/guarded-image-stage/`, session
  **3487a42f960b47f887ddcada151a269a**. Its 12 files and previously archived
  42 approved helpers remain unchanged.
- Sensor-feed failure: `.runtime/guarded-image-stage-recovery-1/`, session
  **82dc1b816889471f98fd25ee8d31ea95**. All 24 non-cache files, raw reader's
  263 files, old review/approval and exact **43 approved helpers** were bound
  and archived before editing. Its 12 cache files remain in place, unchanged.
- Preservation record SHA256:
  `e2a57b04d73a68991bdec3a3e2725e713577c2810a9e56a74918044c138ec6e9`.

Admission rechecks the old evidence hashes and stopped fault states. It also
checks exact cache filenames, sizes, file identities and modification times,
rejecting links, missing/extra/changed files. Metadata checks do not replace the
approved worker's full compressed/hash and expanded-stream verification. There
is no repair or download fallback. Neither old cache nor fault is reset, moved,
copied or updated by the new worker.

## Exact proposed operation

Review SHA256:
**`fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232`**.
Machine-readable package:
`.runtime/verification-review/fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232/review.json`.

Fixed new namespace: **`.runtime/guarded-image-verification-1/`**, unused.
Separate approval: **`image-verification-approval.json`**, absent. The disabled
template cannot authorize work, and neither spent image approval can authorize
this verification. No arbitrary namespace or reset option exists.

One guarded worker will open the retained configuration and all 11 compressed
layers read-only, **3,951,095,908 bytes total**. It rechecks their pinned size/hash
and all expanded diff IDs from the beginning, because partial stream work left
no completion receipt. It produces metrics and one structured verification
result, never tar extraction, an imported image, an engine or model execution.
It has no registry/downloader call path; this is code-enforced, not a new Windows
firewall policy. Cache identity is checked before and after reading as well.

| Control | Limit |
| --- | --- |
| Image | Same pinned Linux amd64 `nvidia/cuda`, manifest `435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c` |
| Worker | One logical processor, 128 MiB committed memory, one process |
| CPU reader | Existing unchanged 256-MiB/four-process job and 1,920-sample contract |
| Admission | <=92 C continuously for ten seconds; baseline wait <=90 seconds |
| Stop | >=97 C; known throttling, sensor/controller/worker failure or cancellation |
| Unknown throttle/source | Same previously accepted image-only limitation; raw readings remain unvalidated/null |
| Work | <=1,800 seconds, <=600 seconds per blob, outer <=1,910 seconds |
| Liveness | Controller/monitor 2.5 seconds, worker progress 7.5 seconds |
| Shutdown | Cooperative cancellation then owned-job termination; five-second worker confirmation budget |
| Expanded data | <=16 GiB total/per layer, <=64-KiB inflate output chunks; no output files |
| Disk | Retain existing 3.95-GB cache; new result/metric namespace <=4 MiB; same 20-GiB host reserve |
| WSL | Existing approved temporary one CPU / 6 GiB / zero swap; fresh preflight checks |
| Attempts | One, including a failed admission/setup after claiming; no automatic retry |

The accepted source and thermal-policy hashes are unchanged. This is a narrower
verification-only workload, never permission for import/build/runtime. Firmware
freshness/calibration, unknown throttle and a physical thermal cutoff remain
limitations; software stopping is not a physical guarantee. Administrator consent
is needed later for the same passive ASUS reader; no prompt or reader ran now.

## Offline validation and final gates

**232 proposal tests pass.** They cover raw-frame replay, rejection without
sequence commitment, redacted reader/OS errors, closed-reader buffered frames,
cache corruption/mutation, absent and spent approvals, helper/evidence changes,
scope/enable flags and no downloader fallback.

**Six native cache-verification cases pass** with tiny generated blobs and fake
frames: success, simulated heat, injected reader exit, injected sharing error,
blocked cache read and cancellation. Every worker/reader stop and restart
rejection was confirmed; fixture cache contents stayed unchanged. Evidence:
`.runtime/cache-verification-rehearsals/cbe674027e7a4c7b882dc4360e16ee23/result.json`.
The shared guard's **17 existing native cases pass again**, including abrupt
owner death and monitor/controller loss:
`.runtime/guarded-image-rehearsals/8ba5bac91ae1463491e35e460e3b1cb7/result.json`.
These fixtures use shortened timings and no real sensor, downloaded blob bodies,
network, Docker or GPU. Full ten-second/97-C controls remain covered by offline
real-format tests. They do not establish reliability of the live source.

`run-verification` was checked with the new approval absent: exit 3,
IMAGE_VERIFICATION_NOT_APPROVED, no new namespace, sensor, worker or cache-body
read. The prepared administrator launcher parses but has not executed. The
first-build packet was separately refreshed while remaining disabled; no compiler
or image import ran. Existing configurations and all WSL/power/firmware settings
were preserved. No account usage was checked and no commit was made.

CLI: `prepare-verification`, `review-verification`, `run-verification`,
`cancel-verification`. The fixed future launcher is
`.runtime/verification-recovery/7ce23bea0a5848529330874891b08013/run-verification-approved.ps1`.
It checks the exact packet and Python binary and invokes the guarded CLI once
after explicit approval. It cannot grant its own approval or reset either fault.

**Approval requested:** one retained-cache verification attempt under these
unchanged hardware limits, with the original feed failure's cause still unproved.
Download/import/compilation/model remain disabled. Import and subsequent build
preparation remain separate later approvals after successful verification.
