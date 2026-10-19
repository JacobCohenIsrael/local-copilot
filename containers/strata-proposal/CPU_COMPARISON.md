# CPU comparison and bounded shutdown — 17 October 2026

Historical checkpoint: the 75/80 C values below were superseded by the owner's
approved 92 C start / 97 C stop CPU-build revision. See NEXT_STEPS.md and the
hash-bound thermal approval; do not reapply these historical thresholds.

## Updated passive comparison through the supervised reader

The owner requested a retry of the canceled Windows administrator launch and
approved the new prompt. The hash-checked helper exited with code 0. The fixed
reader returned ten real samples numbered 1-10 over 8.996 seconds:
95,87,81,77,74,75,75,78,75,78 C. Intervals were 0.974-1.020 s and returned
query times 7.69-31.35 ms. No query error occurred, and the reader stopped.
Evidence: `.runtime/compiler-guard/99766c3642bd4773af3121e5595e3631/probe-result.json`.
Launch/source hashes: `.runtime/compiler-guard/43b26afc371048e6b5c4fc8e9f63b1d4/`.
Reader SHA256: `e8a3db7155b4ef177344d12bc1326f02f5da16ea9bab0a71066a97bb0c67b90d`.

The owner then reported Armoury CPU readings **78,73,67,82,93,95 C**. The two
ranges overlap and both vary, supporting the candidate reading's plausibility.
They are not paired timestamped readings and establish neither a fixed offset
nor exact agreement. The short observation shows changing source values and
reader delivery; it cannot establish a worst-case firmware update bound or
sustained monitoring guarantee. The passive/manual comparison step is complete;
repeat it only if new evidence exposes a discrepancy.

Independent implementation corroboration: G-Helper's
[AsusACPI.cs](https://github.com/seerge/g-helper/blob/main/app/AsusACPI.cs),
reviewed 17 October 2026, names `0x00120094` as `Temp_CPU` and decodes
`DeviceGet` through DSTS with 65536 subtracted. This supports the chosen endpoint
and decoding; it is third-party implementation evidence, not an ASUS calibration
or firmware timing specification. No G-Helper code was installed or executed.

Carry this evidence into CPU-source/build admission review. The reader still
emits validatedCpuSensor=false and hardware throttle=null. No policy activation,
image staging, build, engine, model, GPU load or device-setting change occurred.
The ten-sample probe is not the ten-second cool admission baseline. The remainder
of this file records the earlier checkpoint.

The owner reported Armoury Crate CPU temperature **90–95 °C** during this check.
A hash-checked administrator probe then collected **95, 95, 94 °C** through the
fixed ASUS CPU status endpoint and exited after three samples. No settings or
performance mode were changed. The new samples broadly agree with the owner's
range and show an observed value change; they are not exactly synchronized
measurements or proof of hardware update latency, calibration or safe operation.
`validatedCpuSensor` remains false and CPU hardware throttle remains null.

All these readings exceed the approved 80 °C stop threshold and cannot admit a
build. No compilation, engine execution, model load or GPU test was performed.
The cause of the previous laptop shutdown remains unknown.

Probe evidence: `.runtime/compiler-guard/7e30d8f6fad24e17afeff52dca1458e7/`.
Executed reader SHA256:
`87bf1e5ecc4396a8ad37701a6a3a6ab19604dcec5e36577b872991ebd6e352ed`.
Returned queries took approximately 34, 12 and 10 ms. Those times exclude
initialization/sampling overhead and do not establish future worst-case latency.

The frames exposed integer-overload rounding in the remaining-coverage field.
The reader now explicitly uses double precision; its description-only check
verifies that 2 seconds minus 0.1 seconds yields 1.9 seconds, not 2. This revised
reader was tested without hardware; the evidence above predates that fix.

The guard now shares one five-second deadline across Docker exit-confirmation
operations, beginning at first fault detection before writing the fault record.
It pins the admitted container ID, rechecks identity before control, escalates
from TERM to KILL, and preserves STOP_UNCONFIRMED on outage/deadline/identity
failure. It does not interpret Docker errors as an absent/stopped container.
Removal is separately bounded and separately confirmed. The first fault stays
latched even when exit/removal succeeds; failure details remain in the result.
Emergency stop controls do not depend on mutable policy files being readable.
Sensor/lease setup errors after target verification now also enter cleanup.

**30 unit checks passed**, including simulated Docker outages, hung stop calls,
consumed deadlines, replacement IDs and removal failure. **Five native Docker
rehearsals passed**: synthetic heat, stale feed, lost controller, cancellation
and corrupt sensor data. They used sleeping CPU-only workers with no GPU or
network, and all containers were removed. Confirmed exits took 1.57–1.62 seconds.
Evidence: `.runtime/compiler-guard/verification-c1845cf5fb9143bfbe0b45b461203cd8.json`.

These are tests of the dummy path, not a live Strata guard or a hardware cutoff.
Host/driver/daemon failure and blocked state storage can still prevent timely
action. CPU source update semantics, the actual compiler/controller integration,
disk/download limits and final build-workload approval remain outstanding.
No build is allowed at the current observed temperature. Future admission still
requires fresh validated readings at or below 75 °C for ten seconds; no fan,
power or firmware adjustment is implied or authorized.
