# Approved retained-cache verification: stopped on sample-file access

17 October 2026, **16:14:35-16:15:54 UTC**, including preflight and baseline.
One owner-approved attempt ran under unchanged limits and exact review
`fb7d3db879faec616116dd353e25ac089b4d4e7b1d039bca7eb514c42a8a0232`.
Its receipt is `image-verification-approval.json`. No production helper or
hardware policy was changed during the attempt.

## Result

- Baseline passed, and the verification worker started. Verification did **not**
  complete; no successful worker result or completed expanded-stream receipt exists.
- Terminal state: **FAULT / SENSOR_FEED_ERROR**, CLI exit **3**. Specific detail:
  **OS error 13 (permission denied), operation read, pending sample 71**.
  Last consumed sample was 70; Windows-specific error and reader exit code were
  not available. The rejected frame did not advance the consumed sequence.
- Worker exit and reader shutdown are confirmed. Recorded worker stop time was
  about 0.024 seconds; this is an observation, not a future timing guarantee.
  Worker subsequently reported GUARD_PERMISSION_LOST after permission was revoked.
- All 71 saved raw frames have no recorded sensor error. Their temperatures
  range **73-96 C** and maximum query time is 42.9 ms. Unknown throttle remains
  null; raw validation flags are unchanged. No recorded 97-C event occurred.
- Sample 71 was readable after stopping and contains no sensor error. This
  localizes the current failure to accessing the sample file at that moment.
  A publication/sharing race is a candidate, not a proved Windows error 32 or
  permanent-access diagnosis. The earlier generic failure remains separately
  unproved; do not retroactively assign it this cause.
- Both older attempts' evidence, approvals, archived code and 12 retained blobs
  remain unchanged according to preservation checks. The cache is still
  **3,951,095,908 bytes**. No additional cache-body read/hash workload ran after
  stopping. No retry or reset ran; the new attempt is consumed and latched too.
- Downloads, import, compilation and model execution were disabled throughout.
  Docker inventory is empty and the pinned CUDA image remains absent. No model,
  GPU, firmware, power, fan or existing Strata configuration changes occurred.

## Evidence

Session **429518fb72464042bbaa0e960de2000d** in the fixed namespace
`.runtime/guarded-image-verification-1/`:

- `attempt.json`, `start.json`: exact identity/one-attempt claim.
- `state.json`: fault, specific redacted read diagnostic and confirmed stopping.
  Raw SHA256:
  `bca303d5550de9118b62338b8c5c603971672c1748411236f8fc025ea1ed2826`.
- `metrics.jsonl`, `worker-error.json`: 70 consumed readings and guard revocation.
- Raw reader: `.runtime/compiler-guard/278afc85eaec4534a0e41f091aa5e751/`,
  71 immutable sample files and its raw journal.
- Fresh swap/storage proof:
  `.runtime/image-storage/0d28dfadc09b41c1a229d823a91f4a29/result.json`.
- Launcher invocation/completion, CLI output and structured observational summary:
  `.runtime/verification-recovery/7ce23bea0a5848529330874891b08013/verification-*.json`.
- Exact 46 approved helper snapshots, review and decision are archived under
  `verification-approved-helpers/`, `verification-approved-review.json` and
  `verification-approved-decision.json` in that directory.
  `verification-code-preservation.json` binds those helpers and all current
  attempt/reader files before any future correction.

Both older state hashes remain unchanged:
`3729dbd7aa432cf22441b347e49a5036f9415cdd07c7e7c97d7755e2327e1ecc`
and `dbad7dfedf8e18c58c3a58044f08c38e3dd71aa7ab9ebecf52d4870cb6417859`.
The fixed new launcher's completion is recorded and it must not be invoked again.

## Left

Use offline fixtures to reproduce and correct the sample publication/read access
failure while retaining immutable-frame provenance, age limits, stopping and
specific errors. Preserve all three attempts and their exact reviewed code
before edits. Then prepare a concrete new verification recovery for approval;
no existing approval authorizes another execution. Import/build/model remain
later, separately reviewed steps. No new recovery is prepared by this report.

Later offline preparation update: the sample access conflict is reproduced with
a held publication DELETE handle, and a bounded read-only sharing correction
passes the native fixture. See
[SAMPLE_ACCESS_RECOVERY_REVIEW.md](SAMPLE_ACCESS_RECOVERY_REVIEW.md) for the separate
unused successor awaiting approval. All three states and the retained cache are
unchanged. No new real sensor read or downloaded-blob verification ran.
