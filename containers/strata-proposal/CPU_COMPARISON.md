# CPU comparison and bounded shutdown — 17 October 2026

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
