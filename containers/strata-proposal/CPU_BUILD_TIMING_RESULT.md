# Linux Strata Docker build: complete

18 October 2026. **The approved CPU-only build completed all 153 steps and
exported the Linux Strata executable, supporting library and build metadata.**
This closes the Linux compilation milestone. A real model/API answer and a
Codex-submitted coding task remain to be demonstrated.

## Done

- Built the pinned Strata 0.1.44.1 source in the already-imported CUDA image,
  targeting architecture 86 without vision. Docker records exit zero after
  approximately 18.5 minutes of container execution.
- Exported and independently rechecked file sizes, SHA256 identities and ELF
  headers without executing the artifacts:

| Artifact | Bytes |
| --- | ---: |
| `strata` | 66,712,312 |
| `libstrata_kq.so` | 12,488,600 |
| `BUILD.json` | 234 |

Artifacts: `.runtime/build-artifacts/396b42e0250f46608fe9a21280b9ff36/files/`.
The adjacent `result.json` binds every file/hash, the exact build plan and
container, with non-synthetic provenance and acknowledged export.
Strata SHA256: `6502fa3be3a4fe59060bd151662eb17e8f2c5e2ab119587cc5ca52842807a005`.

- Confirmed successful owned stopping and cleanup; the successful compiler
  container was removed as reviewed. Docker exit/destroy events and a fresh
  absence inspection confirm it is gone. All four recorded host process
  identities (launcher, parent, watchdog and reader) have exited.
- Retained all previous failed attempts, containers, logs, raw readings, cached
  blobs and deferred device evidence. Existing WSL/Docker configuration hashes
  and all 66 reviewed helper identities remain unchanged.

## Controls and evidence

The one-attempt 1.5-second query/readiness allowance was used with unchanged
92 C admission, ten-second baseline, 97 C stop, 2.5-second freshness/leases,
one CPU, 4 GiB compiler memory, one job and 1,800-second build deadline.
WSL remained at one CPU, 6 GiB and no swap. There was no new image download/import,
GPU exposure, model execution, policy extension, retry or fault reset.

All 1,195 raw frames are preserved: 85–96 C and maximum query duration 0.334 s.
No native query needed more than the old one-second budget in this run; success
does not prove the earlier latency event cannot recur. Firmware calibration and
refresh remain unverified, raw validation false and hardware throttle unknown.

Review: `5201aa43ea96c130e96b1b89cd97c9d913919a86e6f14b748783aaa682005fc5`.
The frozen review folder contains the actual owner decision, structured execution
result, metrics, Docker observations and an execution-preservation manifest.
The successful container's full daemon log was removed by successful cleanup
before the final log copy; that failed read is preserved explicitly. Final
153/153 progress was observed live. Artifact hashes, export acknowledgement,
exit-zero/destroy events and the host process exit checks are retained.

## Left

1. Prepare a concrete model-runtime configuration using the exported artifacts
   and read-only existing model mounts; review its actual memory/GPU envelope.
   The temporary 6-GiB WSL build budget is not approved model-runtime sizing.
2. Approve that exact runtime scope and obtain one real Strata API answer in Docker.
3. Submit one bounded OpenCode edit from Codex, return its patch/result and confirm
   worker/Strata shutdown. Keep tuning, MCP and UI deferred until this proof.

`.runtime/cpu-build-timing-1` and its approval are consumed. Model/GPU execution
remains disabled. No new build, automatic restart or historical cleanup is authorized.
