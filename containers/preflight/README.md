# CPU-only Docker preflight

This is a fixed diagnostic, not a Strata launcher or the live safety supervisor.
The default command saves a plan without contacting Docker. `--execute` runs
only the pinned Python probe. No Strata setup, engine, server, CUDA tools,
benchmarks, OpenCode, sensor queries, or model content reads occur.

```powershell
python -B containers/preflight/run.py
python -B -m unittest discover -s containers/preflight -p 'test_*.py' -v
# Execute only after reviewing the generated plan:
python -B containers/preflight/run.py --execute
```

The diagnostic may pull approximately 20 MB of compressed image layers, plus
metadata. It uses the official Python image's Linux amd64 manifest digest:
`sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8`.
That image is not a Strata image and cannot establish Strata runtime compatibility.

The fixed execution settings are 0.5 CPU, 256 MiB RAM, zero swap, 32 processes,
non-root user, read-only root and bind mounts, no capabilities, no new privileges,
no network, no ports, runtime `runc`, no GPU/device requests, no restart, and a
20-second attached runtime deadline. Pulling the image has a separate 180-second
deadline. The host reads the existing JSON configuration only to translate the
already identified model paths. It passes no executable or arbitrary engine
arguments from that configuration into Docker. The probe only queries metadata
for the expected files/directories. It never opens a GGUF or model BIN file.

Before starting, the runner inspects the actual container settings and requires
the exact expected read-only mounts. Cleanup targets only its created container
ID after verifying its ownership label. Failed inspections never start the
container. A runtime timeout enters cleanup, which forcibly removes that same
diagnostic container. Each Docker inspection/removal has a 30-second deadline;
if the Docker daemon becomes unavailable, cleanup can fail and is recorded, not
guaranteed. This runner is not yet a supervisor for host crashes or parent death.
No global Docker cleanup or changes to other workloads are performed.

Evidence is written under `.runtime/strata-preflight/<session>/`: `plan.json`,
`container-before.json`, `probe.json`, and `result.json`. Original Strata launcher,
configuration, Dockerfile, and entrypoint hashes are compared before and after.
Weights are neither hashed nor loaded. Probe booleans describing actions are
scope declarations; the supplied source and inspected launch command establish
which code actually ran. No thermal safety or GPU compatibility is established.

On 16 October 2026 session `3bf3cedcafa0` passed all checks, exited zero after
about 0.4 seconds, and was removed. `/proc/meminfo` reported 16,569,262,080 bytes
(15.43 GiB), while `memory.max` enforced 268,435,456 bytes (256 MiB). Existing
Strata files matched their original hashes. The diagnostic limits are separate
from the simulation policy and do not approve a live model operating envelope.

Next: implement/test Docker lifecycle supervision with a harmless dummy worker
and synthetic telemetry, then prepare a pinned Strata Linux build plan and
separate Linux configuration for review. Actual model startup and policy
activation still require explicit owner approval. Do not run the upstream
entrypoint against the existing data volume as a diagnostic.
