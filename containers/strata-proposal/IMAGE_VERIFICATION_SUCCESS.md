# Retained image verification completed

17 October 2026, **17:54:36-17:57:59 UTC**, about 3 minutes 23 seconds including
preflight and CPU baseline. The owner approved one attempt under exact review
`cd28c631f1e82edc58a4273ea9798009d566a5a46c36a942db260b860562254b`.
The recorded decision is `image-verification-recovery-approval.json`.

## Result

- **COMPLETE, fault null, CLI exit 0.** Configuration and all **11 layers**
  passed pinned compressed size/hash and expanded diff-ID checks.
- Verified compressed input: **3,951,095,908 bytes** including configuration.
  Verified expanded streams: **7,454,964,736 bytes**. Stream status is
  **STREAMS_VERIFIED_NOT_IMPORTED**. No tar files were extracted or written.
- **Zero network requests** from the verification worker. The existing cache
  stayed unchanged; no download, cache copying or repair occurred.
- Worker exit and passive CPU reader shutdown are confirmed. Worker exit was
  already observable during cleanup (recorded confirmation check about 0.0003 s).
- The approved ten-second <=92-C baseline passed before the worker started.
  All **194 raw frames were consumed**, with zero frame errors and no sensor-feed
  exception. Recorded temperatures range **73-96 C**; maximum query time was
  94.2 ms. The sample reader continued through the former sample-71 failure point.
- Unknown hardware throttle remained null and raw validation flags stayed false;
  the accepted image-only source qualification was used without changing originals.
- All **three previous fault states**, raw readings, approval receipts and exact
  reviewed code remain unchanged. The 12 retained blobs also match their pinned
  verification and pre/post metadata identity. No extra body read/hash workload
  ran after the approved worker stopped.
- Downloads, import, compilation and model execution remained disabled. Docker
  has no remaining containers and the pinned CUDA image is still absent from its
  image store. No GPU, firmware, power, fan, WSL or existing Strata settings changed.
- The read-only swap/storage preflight exited and removed its fixture; guest swap
  was zero and the approved resource envelope passed.

## Preserved evidence

Session **e21da7b06fdc4fab903af2efec885f54**, fixed namespace
`.runtime/guarded-image-verification-2/`:

- `attempt.json`, `start.json`: one-attempt identity and reviewed scope.
- `state.json`: COMPLETE, result and positive stopping confirmations. Raw SHA256:
  `41139a44d3e5902eab88f94f07b1e7c83a14c276d2e3142a7b736cf949cad15f`.
- `worker-result.json`: configuration/input counts and all ordered compressed/
  expanded layer hashes. Raw SHA256:
  `6d9c3bbbb7f1a0f79c711aa475522774f403abaa05483a08bd5d208600ce1b41`.
- `metrics.jsonl`: 194 consumed real observations.
- Raw reader: `.runtime/compiler-guard/2a5cc9fcdcb940ac94d5a8d452d3e67e/`.
- Swap/storage proof:
  `.runtime/image-storage/f7b1d5e946fc47c886509fc0e94ece62/result.json`.

Launcher invocation/completion, CLI output and structured summary are under
`.runtime/sample-access-recovery/1b947a961afc4641bffa8be3b94c926d/`.
The outcome is `verification-outcome.json`. The exact **48 approved helper
snapshots**, review and decision are saved under `verification-approved-helpers/`,
`verification-approved-review.json` and `verification-approved-decision.json`.
`verification-code-preservation.json` binds those snapshots and current attempt/
reader files, SHA256:
`23a48f19ab38b5b198ef9cc663f5457f57e7979a9ad87a4721ec0dcae2c7467f`.

The successful claim is also consumed. Do not rerun its launcher, clear its
state or treat this approval as authority for import or other work. The earlier
three attempts remain preserved separately, each with its original fault.

## Left

Prepare the bounded Docker image-import operation for separate review: verified
retained input, actual backing-volume/storage bounds, monitored resource use,
deadline, independent stopping, disk reserve and cleanup evidence. Stream byte
verification alone does not bound Docker daemon disk allocation.

After approved import and image readiness, refresh the disabled first-build
packet and obtain the exact CPU-source/workload approval for one capped build.
Compilation and the first real Strata coding task remain later milestones;
runtime/model/GPU policy is still unapproved. No import/build/model action was
prepared as an execution permission by this result report. No commit was made.
