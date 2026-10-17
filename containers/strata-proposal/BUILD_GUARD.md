# Compiler sensor/guard connection — 16 October 2026

The prepared package now has a guard contract at
`.runtime/strata-build/1537f5ec/guard-contract.json`, binding its compiler manifest
hash, exact target name/image/arguments, read-only inputs, resource limits, and
CPU reader hash. The actual compiler matcher rejects changed identity/image,
GPU requests and writable source mounts. No compiler was created or started;
the CUDA base image was not pulled.

`build_guard.py` supplies the matcher, sensor contract and independent watchdog.
`cpu_reader.ps1` reads only the existing ASUS CPU-temperature status endpoint.
Samples carry sequence, timestamp, query duration, source, explicit validity
and unknown throttle status. Immutable bounded sample files avoid a Windows
sharing race observed with replacement of a file another process was reading.
After initial discovery the guard checks successive frame names rather than
rescanning history. Each frame is capped at 4 KiB; a session at 2,048 frames.

The reader defaults to three samples. Following approval of the build-only
exception it has a hard request ceiling of 1,920 samples and 32 minutes, fixed
monotonic sample slots and declared remaining coverage. It uses two-second CIM
timeouts and exits after a returned query exceeds the approved one-second limit.
The independent guard must still stop work on stale data if a query hangs. It has no
self-elevation, arbitrary vendor endpoint, installer or device-writing method.
Only the three-sample run was exercised; long-run behavior remains unvalidated.
The historical saved contract predates that reader update; `build_guard.py`
reports the new reader hash. Rebind and validate it before any future build.
See `BUILD_POLICY_REVIEW.md` for the approval record and coverage tests.

## Results

- Nine mocked checks passed, covering archive safety, compiler matching,
  sensor validity/freshness/replays, missing channels and disabled approval.
- Four real Docker rehearsals passed: synthetic heat, stale sensor while the
  controller stayed alive, controller loss while the sensor remained fresh,
  and cancellation. All used one CPU / 4 GiB / zero swap / 128 processes,
  but a pinned Python image, no network, and a sleeping worker/descendant.
  Each persisted the first fault, stopped the uncooperative target (exit 137),
  and verified removal. No compiler, source code or model ran in these cases.
- The real hash-checked administrator reader completed three CPU candidate
  readings: **94, 94 and 83 °C**, then exited. Query times were approximately
  33, 8 and 7 ms, excluding initialization and sampling intervals; this is not
  a complete monitor overhead benchmark. No persistent helper was installed.
- Channel checks at those samples' recorded times returned
  `CPU_THROTTLE_MISSING`; `validatedCpuSensor` remains false. Historical samples
  are evidence, not fresh admission data or a completed calibration.

The rehearsal's 85 °C trip, 1.5-second freshness/lease limits, one-second stop
grace and 15-second deadline apply only to harmless test targets. They are not
an approved live build policy. Actual compiler admission returns
`BUILD_NOT_APPROVED`; there is no start/build command, live-enable flag,
automatic reset or policy-approval authority in this module.

CPU hardware throttle status remains unknown. The owner approved that exception
for CPU-only compilation on 16 October 2026; do not request that decision again.
Sensor meaning/freshness validation and implementation/validation of the approved
live deadlines and monitor/watchdog failure behavior remain unresolved. The
real compiler matcher was tested against mocked inspection data; only the
Python stand-in ran in Docker. Before compilation, satisfy the remaining gates
and obtain approval of the final executable build manifest/workload.
Do not silently waive a channel or substitute OS frequency limits. Model
loading requires separate approval. Existing installation, driver, firmware,
fan and power settings remain unchanged.
