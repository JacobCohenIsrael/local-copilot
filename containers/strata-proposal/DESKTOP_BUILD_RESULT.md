# Docker import and first CPU build: execution result

18 October 2026. **CUDA import succeeded; the Strata build failed at startup.**
No Linux Strata artifact was produced. No model or GPU workload ran.

## Done

- The owner approved the exact combined operation and accepted its CPU-source
  and shared-Docker cancellation limitations. Review SHA256:
  `35f7e4b766ef0fd25c99de44428ab49bcca1a4a53254c4f384b96a6485163e78`.
- Rehashed the retained blobs into a 3,951,112,704-byte OCI archive, imported it
  once into ordinary Docker Desktop storage, and verified the pinned image's
  manifest/platform and ordered layer identities. The archive and image remain.
- The importer and its reader stopped cleanly. The connected CPU build received
  the exact delegated approval, rechecked its inputs, passed fresh admission and
  started its restricted container once. No resource or policy increase occurred.

## Build failure and stopping

Docker events show container
`3372f9072cc2089354063879297363374d166938548e6dcad5ec62ad3336df55`
started and exited with code **1 after 0.151 seconds**. The watchdog latched
`UNEXPECTED_WORKER_EXIT`; the launcher returned exit 3. This was not a recorded
temperature fault. The exact startup cause remains unconfirmed.

Automatic cleanup removed the container before its logs were captured. A removal
error left the original guard record at `cleanupComplete: false`; later Docker
events and an immutable-ID inspection confirm the container is absent. Preserve
the original record without rewriting it. A subsequent process check found no
matching importer, supervisor, build watchdog or build-reader process, and the
administrator wrapper had exited. No automatic retry or fault reset occurred.

The import recorded 288 real samples at 72-96 C; the build reader recorded 72
at 87-94 C. Raw sensor validation remains false and hardware throttle remains
unknown, as accepted. WSL stayed at one CPU / 6 GiB / no swap, and the WSL and
Docker Desktop configuration hashes are unchanged. All four previous image
attempts and the deferred native rehearsal evidence remain unchanged.

## Evidence and next step

The exact review directory under `.runtime/desktop-test-review/` contains
`execution-result.json`, `execution-preservation.json`, owner/delegated decisions,
Docker events/inspection results and process-stop observations. The preservation
manifest binds both new attempts, both raw reader sessions and launcher output.
The large OCI archive is bound by its validated stream receipt and file metadata;
it was not rehashed again during evidence capture. Original approved helpers are
already frozen beside the review. Both execution approvals are now consumed.

- Left: diagnose startup and correct bounded failure-log preservation and cleanup
  reporting offline, then prepare a new CPU-only build attempt for approval.
  Reuse the imported image; no new download/import is needed.
- Then: obtain Linux Strata, prepare the separate model-runtime scope, get a short
  API answer and complete the first OpenCode edit submitted by Codex.

The failed attempt is retained at `.runtime/first-cpu-build/`; do not reset or
reuse it. Keep the existing limits. Model execution remains disabled.
