# Offline validation, 20 October 2026

**Done offline; no live execution or shutdown proof is claimed.**

Final frozen review SHA256:
`3bfff04625a3a2cb4eb14efe6e32b79335fb9bb3534da810fc439e1708c098ab`.

Packet:
`.runtime/strata-manual-chat-review/3bfff04625a3a2cb4eb14efe6e32b79335fb9bb3534da810fc439e1708c098ab/review.json`.

- **28 manual-chat tests passed.** They exercise the real controller loop against
  fake Docker/API/watchdog inputs, one user prompt and reply, explicit owned stop,
  uncertain delivery without resend, partial timeout, consumed failed preflight,
  exact approval admission, actual guest lease logic, emergency-stop latching,
  advisory startup warnings, the separate watchdog loop, text/token/byte limits,
  conversation commands, SSE decoding, Unicode transport, terminal control
  filtering, serialized review acceptance and staged-input mutation rejection.
  Two new CLI checks cover a clear missing-approval message and preserved
  diagnostics for other errors.
- **24 existing runtime tests passed** in a separate process. These cover the
  reused no-restart wrapper, kernel qualification, telemetry gate, container
  isolation/ownership, leases, deadlines and connected fake runtime failures.
- Eight Python sources parsed successfully; the PowerShell launcher passed syntax
  parsing without execution. `chat.py status` reported no manual approval,
  no manual attempt and no state.
- The real offline preparation verified the preserved successful build, cached
  runtime, pinned source tree against its archives, existing model-file identities
  and unchanged machine-setting files. It staged seven guest/config inputs and
  froze 104 exact helper sources. All 104 source snapshots matched their hashes.
  No engine/native tokenizer import or hardware query was used for these checks.
- The final real `chat.py review` passed, with model launch false and approval
  absent. A measured review took 0.083 seconds; the expensive full source check
  occurs before live helpers. That timing is an observation, not a guarantee.

## Corrections and preserved offline failures

The first test run had three Windows sandbox temporary-directory errors. Test
fixtures now stay under `.runtime/manual-chat-offline-tests/`; no permissions
were changed. Early connected-test fixtures used a nonserializable mock PID and
typed before READY; those test records remain in that offline namespace.

Initial review `fd876cca0bc5ad11980252d3bdee0aaef772cbbc4f21bbc0b94b39c6a8845267`
was superseded during implementation. Review
`a4494c067a8b29004de42f9437e7400ef6544a16e1f58629159dd37a7e77969e`
exposed tuple/list comparison after JSON serialization and was rejected offline.
Canonical comparison fixes that review-format defect; the regression also
rejects a changed staged input. Both earlier packets, packages and unapproved
templates remain retained. None authorized or launched a model.

A source scan initially sat on the startup reauthorization path. Its measured
53.816-second runtime would exceed the controller lease. It was moved to the
offline/preflight path before live helpers; fast review still checks source-plan,
helper, configuration and staged-input bindings. No guard was weakened.

The owner's first manual launch was refused with `MANUAL_CHAT_NOT_APPROVED`:
no approval existed, so no live preflight, Docker/model operation, session claim
or attempt consumption occurred. The CLI now prints a plain explanation instead
of a traceback for this exact condition. Other errors retain their diagnostics.
The real missing-approval CLI path was checked offline and still refuses before
live access. The previously sealed 26-test review
`1dc9d6a0934fe0c7991b7e5c31ec12b67e60410b6414bac20bb6e1447307c4da`
remains preserved; only a fresh offline packet was prepared for the CLI fix.

## Left

Fresh approval for the exact [launch review](LAUNCH_REVIEW.md), followed by one
manual session and independent stopped/PID-0 and helper-exit evidence. The current
review still proposes 150 seconds per request and 300 seconds total model lifetime.
The 4K output cap is a ceiling; consuming it within that time is unproven and
unlikely at the last observed decode rate. Increasing time or input requires a
new reviewed proposal. No automated next attempt or reset is included.

All fifteen previous model attempts remain consumed. Manual `approval.json` and
the real manual-session namespace remain absent. Only this workstream's new
`containers/manual-chat/` sources/docs and separate `.runtime/` preparation/test
evidence were written. Shared experiment files and plans were not edited here.
